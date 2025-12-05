import { cr as asClassComponent$1, cs as async_mode_flag, ct as createClassComponent } from './async-DSsyBdZ5.js';
import { r as render } from './index-CVCLyXDH.js';

/** @import { SvelteComponent } from '../index.js' */

/** @typedef {{ head: string, html: string, css: { code: string, map: null }}} LegacyRenderResult */

/**
 * Takes a Svelte 5 component and returns a Svelte 4 compatible component constructor.
 *
 * @deprecated Use this only as a temporary solution to migrate your imperative component code to Svelte 5.
 *
 * @template {Record<string, any>} Props
 * @template {Record<string, any>} Exports
 * @template {Record<string, any>} Events
 * @template {Record<string, any>} Slots
 *
 * @param {SvelteComponent<Props, Events, Slots>} component
 * @returns {typeof SvelteComponent<Props, Events, Slots> & Exports}
 */
function asClassComponent(component) {
	const component_constructor = asClassComponent$1(component);
	/** @type {(props?: {}, opts?: { $$slots?: {}; context?: Map<any, any>; }) => LegacyRenderResult & PromiseLike<LegacyRenderResult> } */
	const _render = (props, { context } = {}) => {
		// @ts-expect-error the typings are off, but this will work if the component is compiled in SSR mode
		const result = render(component, { props, context });

		const munged = Object.defineProperties(
			/** @type {LegacyRenderResult & PromiseLike<LegacyRenderResult>} */ ({}),
			{
				css: {
					value: { code: '', map: null }
				},
				head: {
					get: () => result.head
				},
				html: {
					get: () => result.body
				},
				then: {
					/**
					 * this is not type-safe, but honestly it's the best I can do right now, and it's a straightforward function.
					 *
					 * @template TResult1
					 * @template [TResult2=never]
					 * @param { (value: LegacyRenderResult) => TResult1 } onfulfilled
					 * @param { (reason: unknown) => TResult2 } onrejected
					 */
					value: (onfulfilled, onrejected) => {
						if (!async_mode_flag) {
							const user_result = onfulfilled({
								css: munged.css,
								head: munged.head,
								html: munged.html
							});
							return Promise.resolve(user_result);
						}

						return result.then((result) => {
							return onfulfilled({
								css: munged.css,
								head: result.head,
								html: result.body
							});
						}, onrejected);
					}
				}
			}
		);

		return munged;
	};

	// @ts-expect-error this is present for SSR
	component_constructor.render = _render;

	// @ts-ignore
	return component_constructor;
}

/**
 * Runs the given function once immediately on the server, and works like `$effect.pre` on the client.
 *
 * @deprecated Use this only as a temporary solution to migrate your component code to Svelte 5.
 * @param {() => void | (() => void)} fn
 * @returns {void}
 */
function run(fn) {
	fn();
}

const noop = () => {};

var f = /*#__PURE__*/Object.freeze({
	__proto__: null,
	asClassComponent: asClassComponent,
	createBubbler: noop,
	createClassComponent: createClassComponent,
	handlers: noop,
	nonpassive: noop,
	once: noop,
	passive: noop,
	preventDefault: noop,
	run: run,
	self: noop,
	stopImmediatePropagation: noop,
	stopPropagation: noop,
	trusted: noop
});

export { asClassComponent as a, f };
//# sourceMappingURL=legacy-server-U-epADY3.js.map
