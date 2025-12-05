const EACH_ITEM_REACTIVE = 1;
const EACH_INDEX_REACTIVE = 1 << 1;
/** See EachBlock interface metadata.is_controlled for an explanation what this is */
const EACH_IS_CONTROLLED = 1 << 2;
const EACH_IS_ANIMATED = 1 << 3;
const EACH_ITEM_IMMUTABLE = 1 << 4;

const PROPS_IS_IMMUTABLE = 1;
const PROPS_IS_RUNES = 1 << 1;
const PROPS_IS_UPDATED = 1 << 2;
const PROPS_IS_BINDABLE = 1 << 3;
const PROPS_IS_LAZY_INITIAL = 1 << 4;

const TRANSITION_IN = 1;
const TRANSITION_OUT = 1 << 1;
const TRANSITION_GLOBAL = 1 << 2;

const TEMPLATE_FRAGMENT = 1;
const TEMPLATE_USE_IMPORT_NODE = 1 << 1;
const TEMPLATE_USE_SVG = 1 << 2;
const TEMPLATE_USE_MATHML = 1 << 3;

const HYDRATION_START = '[';
/** used to indicate that an `{:else}...` block was rendered */
const HYDRATION_START_ELSE = '[!';
const HYDRATION_END = ']';
const HYDRATION_ERROR = {};

const ELEMENT_IS_NAMESPACED = 1;
const ELEMENT_PRESERVE_ATTRIBUTE_CASE = 1 << 1;
const ELEMENT_IS_INPUT = 1 << 2;

const UNINITIALIZED = Symbol();

// Dev-time component properties
const FILENAME = Symbol('filename');
const HMR = Symbol('hmr');

const NAMESPACE_HTML = 'http://www.w3.org/1999/xhtml';
const NAMESPACE_SVG = 'http://www.w3.org/2000/svg';
const NAMESPACE_MATHML = 'http://www.w3.org/1998/Math/MathML';

// we use a list of ignorable runtime warnings because not every runtime warning
// can be ignored and we want to keep the validation for svelte-ignore in place
const IGNORABLE_RUNTIME_WARNINGS = /** @type {const} */ ([
	'await_waterfall',
	'await_reactivity_loss',
	'state_snapshot_uncloneable',
	'binding_property_non_reactive',
	'hydration_attribute_changed',
	'hydration_html_changed',
	'ownership_invalid_binding',
	'ownership_invalid_mutation'
]);

const ATTACHMENT_KEY = '@attach';

export { ATTACHMENT_KEY as A, ELEMENT_IS_NAMESPACED as E, FILENAME as F, HYDRATION_START as H, IGNORABLE_RUNTIME_WARNINGS as I, NAMESPACE_SVG as N, PROPS_IS_UPDATED as P, TEMPLATE_FRAGMENT as T, UNINITIALIZED as U, HYDRATION_START_ELSE as a, HYDRATION_END as b, TEMPLATE_USE_IMPORT_NODE as c, NAMESPACE_MATHML as d, TEMPLATE_USE_SVG as e, TEMPLATE_USE_MATHML as f, HYDRATION_ERROR as g, HMR as h, NAMESPACE_HTML as i, TRANSITION_GLOBAL as j, TRANSITION_IN as k, TRANSITION_OUT as l, PROPS_IS_BINDABLE as m, PROPS_IS_RUNES as n, PROPS_IS_IMMUTABLE as o, PROPS_IS_LAZY_INITIAL as p, ELEMENT_PRESERVE_ATTRIBUTE_CASE as q, ELEMENT_IS_INPUT as r, EACH_INDEX_REACTIVE as s, EACH_ITEM_REACTIVE as t, EACH_ITEM_IMMUTABLE as u, EACH_IS_ANIMATED as v, EACH_IS_CONTROLLED as w };
