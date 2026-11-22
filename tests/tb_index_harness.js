/**
 * @fileoverview Runs index.html's inline script against a stub DOM.
 *
 * Usage: node tb_index_harness.js <script.js> <scenario.json>
 *
 * The scenario names what fetch('episodes.json') does. The harness runs
 * the script, lets its promises settle, and prints one JSON object:
 *   eplist: the #eplist subtree (tag, attrs, props, classes, text, kids)
 *   sinks: every string written to an HTML parsing sink (innerHTML etc.)
 *   unknown: every read of a DOM member the stub does not implement
 *   errors: uncaught errors and unhandled rejections
 *   fetches: the URLs passed to fetch
 *
 * The stub is not a browser: innerHTML is recorded, never parsed. The
 * members it implements are listed in KNOWN below.
 */

'use strict';

const fs = require('fs');
const vm = require('vm');

const sinks = [];
const unknown = [];
const errors = [];
const fetches = [];

/** Members a stub node implements; reading any other is logged. */
const KNOWN = new Set([
  'tagName', 'nodeName', 'nodeType', 'id', 'className', 'classList',
  'children', 'childNodes', 'firstChild', 'parentNode', 'textContent',
  'innerText', 'innerHTML', 'outerHTML', 'appendChild', 'append',
  'prepend', 'replaceChildren', 'removeChild', 'remove', 'insertBefore',
  'insertAdjacentHTML', 'insertAdjacentText', 'setAttribute',
  'getAttribute', 'hasAttribute', 'removeAttribute', 'querySelector',
  'querySelectorAll', 'addEventListener', 'select', 'value', 'hidden',
  'title', 'dataset', 'style',
]);

/** Property reads that JS itself makes on any object. */
const IGNORED = new Set(['then', 'toJSON', 'constructor', 'inspect']);

/** A minimal element or text node. */
class Node {
  /**
   * @param {string} tag Lower-case tag name, or '#text'.
   * @param {string=} text Text for a text node.
   */
  constructor(tag, text) {
    this._tag = tag;
    this._text = text === undefined ? '' : String(text);
    this._attrs = new Map();
    this._kids = [];
    this._parent = null;
    this._classes = [];
    this._listeners = {};
    this._props = {};
    this.dataset = {};
    this.style = {};
  }

  get tagName() { return this._tag.toUpperCase(); }
  get nodeName() { return this.tagName; }
  get nodeType() { return this._tag === '#text' ? 3 : 1; }
  get parentNode() { return this._parent; }
  get childNodes() { return this._kids.slice(); }
  get children() { return this._kids.filter((k) => k.nodeType === 1); }
  get firstChild() { return this._kids[0] || null; }

  get id() { return this._attrs.get('id') || ''; }
  set id(v) { this._attrs.set('id', String(v)); }

  get className() { return this._classes.join(' '); }
  set className(v) {
    this._classes = String(v).split(/\s+/).filter(Boolean);
  }

  get classList() {
    const self = this;
    return {
      add(...names) {
        names.forEach((n) => {
          if (!self._classes.includes(n)) self._classes.push(n);
        });
      },
      remove(...names) {
        self._classes = self._classes.filter((c) => !names.includes(c));
      },
      contains(n) { return self._classes.includes(n); },
    };
  }

  get textContent() {
    if (this._tag === '#text') return this._text;
    return this._kids.map((k) => k.textContent).join('');
  }
  set textContent(v) {
    if (this._tag === '#text') {
      this._text = String(v);
      return;
    }
    this._detachAll();
    const s = v === null || v === undefined ? '' : String(v);
    if (s) this._adopt(new Node('#text', s));
  }

  get innerText() { return this.textContent; }
  set innerText(v) { this.textContent = v; }

  get innerHTML() { return '[stub: innerHTML is write-only]'; }
  set innerHTML(v) {
    sinks.push({sink: 'innerHTML', value: String(v)});
    this._detachAll();
  }

  get outerHTML() { return '[stub: outerHTML is write-only]'; }
  set outerHTML(v) { sinks.push({sink: 'outerHTML', value: String(v)}); }

  insertAdjacentHTML(pos, v) {
    sinks.push({sink: 'insertAdjacentHTML', value: String(v)});
  }

  insertAdjacentText(pos, v) { this._adopt(new Node('#text', v)); }

  appendChild(n) {
    if (n instanceof Fragment) {
      n._kids.slice().forEach((k) => this._adopt(k));
    } else {
      this._adopt(n);
    }
    return n;
  }

  append(...nodes) {
    nodes.forEach((n) => {
      this.appendChild(typeof n === 'object' ? n : new Node('#text', n));
    });
  }

  prepend(...nodes) {
    const old = this._kids.slice();
    this._detachAll();
    this.append(...nodes);
    old.forEach((k) => this._adopt(k));
  }

  replaceChildren(...nodes) {
    this._detachAll();
    this.append(...nodes);
  }

  insertBefore(n, ref) {
    if (!ref) return this.appendChild(n);
    const old = this._kids.slice();
    this._detachAll();
    old.forEach((k) => {
      if (k === ref) this.appendChild(n);
      this._adopt(k);
    });
    return n;
  }

  removeChild(n) {
    this._kids = this._kids.filter((k) => k !== n);
    n._parent = null;
    return n;
  }

  remove() { if (this._parent) this._parent.removeChild(this); }

  setAttribute(name, v) {
    const key = String(name).toLowerCase();
    if (key === 'class') {
      this.className = v;
    } else {
      this._attrs.set(key, String(v));
    }
  }

  getAttribute(name) {
    const key = String(name).toLowerCase();
    if (key === 'class') return this.className;
    return this._attrs.has(key) ? this._attrs.get(key) : null;
  }

  hasAttribute(name) {
    return this.getAttribute(name) !== null;
  }

  removeAttribute(name) { this._attrs.delete(String(name).toLowerCase()); }

  querySelectorAll(sel) {
    const match = (n) => {
      if (n.nodeType !== 1) return false;
      if (sel.startsWith('.')) return n._classes.includes(sel.slice(1));
      if (sel.startsWith('#')) return n.id === sel.slice(1);
      return n._tag === sel.toLowerCase();
    };
    const out = [];
    const walk = (n) => n._kids.forEach((k) => {
      if (match(k)) out.push(k);
      walk(k);
    });
    walk(this);
    return out;
  }

  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }

  addEventListener(type, fn) {
    (this._listeners[type] = this._listeners[type] || []).push(fn);
  }

  select() {}

  /** @param {!Node} n */
  _adopt(n) {
    if (n._parent) n._parent.removeChild(n);
    n._parent = this;
    this._kids.push(n);
  }

  _detachAll() {
    this._kids.forEach((k) => { k._parent = null; });
    this._kids = [];
  }

  /** @return {!Object} A JSON-ready copy of this subtree. */
  dump() {
    if (this._tag === '#text') return {text: this._text};
    return {
      tag: this._tag,
      classes: this._classes.slice(),
      attrs: Object.fromEntries(this._attrs),
      props: Object.assign({}, this._props),
      text: this.textContent,
      kids: this._kids.map((k) => k.dump()),
    };
  }
}

/** A document fragment: its children move on append. */
class Fragment extends Node {
  constructor() { super('#fragment'); }
}

/**
 * Wraps a node so unknown reads are logged and unknown writes are kept.
 * @param {!Node} node
 * @return {!Node}
 */
function watch(node) {
  return new Proxy(node, {
    get(target, prop, recv) {
      if (typeof prop === 'symbol' || prop.startsWith('_') ||
          prop === 'dump' || prop in target) {
        const v = Reflect.get(target, prop, target);
        return typeof v === 'function' ? v.bind(target) : v;
      }
      if (prop in target._props) return target._props[prop];
      if (!IGNORED.has(prop)) unknown.push(target._tag + '.' + prop);
      return undefined;
    },
    set(target, prop, v) {
      if (typeof prop === 'symbol' || prop.startsWith('_') ||
          KNOWN.has(prop) || prop in target) {
        return Reflect.set(target, prop, v, target);
      }
      target._props[prop] = v;
      return true;
    },
  });
}

/**
 * @param {*} n A node or its proxy.
 * @return {*} The raw node.
 */
function unwrap(n) {
  return n && n._raw ? n._raw : n;
}

/**
 * @param {!Node} n
 * @return {!Node} The proxy that script code sees for n.
 */
function wrap(n) {
  if (!n._proxy) n._proxy = watch(n);
  return n._proxy;
}

/**
 * @param {?Node} n
 * @return {?Node}
 */
function out(n) {
  return n ? wrap(n) : n;
}

// Script code passes proxies around; the tree holds raw nodes.
Object.defineProperty(Node.prototype, '_raw', {
  get() { return this; },
});
const realAdopt = Node.prototype._adopt;
Node.prototype._adopt = function(n) { realAdopt.call(this, unwrap(n)); };
const realRemove = Node.prototype.removeChild;
Node.prototype.removeChild = function(n) {
  realRemove.call(this, unwrap(n));
  return n;
};
const realInsert = Node.prototype.insertBefore;
Node.prototype.insertBefore = function(n, ref) {
  realInsert.call(this, unwrap(n), unwrap(ref));
  return n;
};
const realAppend = Node.prototype.appendChild;
Node.prototype.appendChild = function(n) {
  realAppend.call(this, unwrap(n));
  return n;
};
const realQsa = Node.prototype.querySelectorAll;
Node.prototype.querySelectorAll = function(sel) {
  return realQsa.call(this, sel).map(out);
};
for (const name of ['parentNode', 'firstChild']) {
  const d = Object.getOwnPropertyDescriptor(Node.prototype, name);
  Object.defineProperty(Node.prototype, name, {
    get() { return out(d.get.call(this)); },
  });
}
for (const name of ['childNodes', 'children']) {
  const d = Object.getOwnPropertyDescriptor(Node.prototype, name);
  Object.defineProperty(Node.prototype, name, {
    get() { return d.get.call(this).map(out); },
  });
}

/**
 * Builds the fetch stub for a scenario.
 * @param {!Object} sc The scenario.
 * @return {function(string): !Promise}
 */
function makeFetch(sc) {
  return function(url) {
    fetches.push(String(url));
    if (sc.fetch === 'reject') {
      return Promise.reject(new TypeError('Failed to fetch'));
    }
    const res = {
      ok: sc.ok !== false,
      status: sc.status || 200,
      statusText: sc.ok === false ? 'Not Found' : 'OK',
      json() {
        if (sc.json === 'reject') {
          return Promise.reject(new SyntaxError('Unexpected token <'));
        }
        return Promise.resolve(JSON.parse(JSON.stringify(sc.body)));
      },
      text() { return Promise.resolve(JSON.stringify(sc.body)); },
    };
    return Promise.resolve(res);
  };
}

/** Runs the scenario and prints the result. */
async function main() {
  const src = fs.readFileSync(process.argv[2], 'utf8');
  const sc = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));

  const byId = {
    feedurl: wrap(new Node('input')),
    copy: wrap(new Node('button')),
    eplist: wrap(new Node('div')),
  };
  Object.keys(byId).forEach((k) => { unwrap(byId[k]).id = k; });

  const document = new Proxy({
    getElementById: (id) => byId[id] || null,
    createElement: (tag) => wrap(new Node(String(tag).toLowerCase())),
    createTextNode: (t) => wrap(new Node('#text', t)),
    createDocumentFragment: () => wrap(new Fragment()),
    querySelector: (sel) => (sel.startsWith('#') ?
      byId[sel.slice(1)] || null : null),
    write: (v) => sinks.push({sink: 'document.write', value: String(v)}),
    writeln: (v) => sinks.push({sink: 'document.write', value: String(v)}),
  }, {
    get(target, prop) {
      if (typeof prop === 'symbol' || prop in target) return target[prop];
      if (!IGNORED.has(prop)) unknown.push('document.' + prop);
      return undefined;
    },
  });

  process.on('unhandledRejection', (e) => errors.push(String(e)));

  const sandbox = {
    document,
    location: {href: 'https://example.invalid/tb/index.html'},
    navigator: {clipboard: {writeText: () => Promise.resolve()}},
    fetch: makeFetch(sc),
    URL,
    console,
    setTimeout,
    clearTimeout,
    Promise,
    JSON,
    String,
    Number,
    Array,
    Object,
    Error,
    TypeError,
  };
  sandbox.window = sandbox;
  sandbox.self = sandbox;

  try {
    vm.runInNewContext(src, sandbox, {filename: 'index.html<script>'});
  } catch (e) {
    errors.push('uncaught: ' + String(e));
  }
  for (let i = 0; i < 5; i++) {
    await new Promise((r) => setImmediate(r));
  }

  process.stdout.write(JSON.stringify({
    eplist: unwrap(byId.eplist).dump(),
    sinks,
    unknown,
    errors,
    fetches,
  }));
}

main();
