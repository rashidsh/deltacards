// ==UserScript==
// @name         deltacards Bridge
// @version      0.2.0
// @description  Connects the Undercards web client to a local deltacards engine instance for offline play and testing.
// @author       rashidsh
// @homepageURL  https://github.com/rashidsh/deltacards
// @downloadURL  https://raw.githubusercontent.com/rashidsh/deltacards/main/deltacards/app/websocket/userscripts/deltacards-bridge.user.js
// @updateURL    https://raw.githubusercontent.com/rashidsh/deltacards/main/deltacards/app/websocket/userscripts/deltacards-bridge.user.js
// @match        https://undercards.net/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=undercards.net
// @run-at       document-start
// @grant        none
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  const PLUGIN_NAME = "deltacards Bridge";

  const DELTACARDS_HOST = 'localhost';
  const DELTACARDS_PORT = 8080;

  const DELTACARDS_BASE_URL = `http://${DELTACARDS_HOST}:${DELTACARDS_PORT}`;
  const DELTACARDS_BASE_WEBSOCKET_URL = `ws://${DELTACARDS_HOST}:${DELTACARDS_PORT}`;

  const SETTINGS_PREFIX = `underscript.plugin.${PLUGIN_NAME}.`;
  const SETTING_DEFAULTS = {
    loadCustomContent: true,
    loadCustomContentEverywhere: false,
  };

  /* Helper functions */

  async function checkStatus() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);

    try {
      const response = await fetch(`${DELTACARDS_BASE_URL}/check/`, {
        method: 'GET',
        cache: 'no-store',
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`Health check returned status code ${response.status}.`);
      }

    } finally {
      clearTimeout(timeout);
    }
  }

  /* Settings helper */

  function readBooleanSetting(key, defaultValue) {
    const rawValue = localStorage.getItem(SETTINGS_PREFIX + key);

    if (rawValue === null) return defaultValue;
    if (rawValue === 'true' || rawValue === '1') return true;
    if (rawValue === 'false' || rawValue === '0') return false;

    return defaultValue;
  }

  function normalizedPathname() {
    const pathname = location.pathname;

    if (pathname.length > 1) {
      return pathname.replace(/\/+$/, '');
    }

    return pathname;
  }

  function getLocalGameID() {
    if (normalizedPathname() !== '/Spectate') {
      return null;
    }

    return new URL(location.href).searchParams.get('deltacardsGameId');
  }

  function shouldEnableInterception() {
    const loadCustomContent = readBooleanSetting(
      'loadCustomContent',
      SETTING_DEFAULTS.loadCustomContent
    );
    if (!loadCustomContent) return false;

    const loadCustomContentEverywhere = readBooleanSetting(
      'loadCustomContentEverywhere',
      SETTING_DEFAULTS.loadCustomContentEverywhere
    );

    const pathname = normalizedPathname();

    if (loadCustomContentEverywhere) return pathname !== '/Game';

    return (
      pathname === '/Spectate'
      && getLocalGameID() !== null
    );
  }

  const interceptionEnabled = shouldEnableInterception();

  let resolveCustomTranslationsReady = () => {};

  const customTranslationsReady = interceptionEnabled
    ? new Promise((resolve) => {
        resolveCustomTranslationsReady = resolve;
      })
    : Promise.resolve();

  /* Custom content */

  let customContent = {
    cards: [],
    artifacts: [],
    enchantments: [],
    souls: [],
  };

  let customIdsByKind = new Map();

  function setCustomContent(value) {
    const contentIds = (
        value.contentIds
        && typeof value.contentIds === 'object'
    ) ? value.contentIds : {};

    customContent = {
      cards: Array.isArray(value.cards) ? value.cards : [],
      artifacts: Array.isArray(value.artifacts) ? value.artifacts : [],
      enchantments: Array.isArray(value.enchantments) ? value.enchantments : [],
      souls: Array.isArray(value.souls) ? value.souls : [],
    };

    customIdsByKind = new Map();

    for (const kind of [
      'card',
      'artifact',
      'soul',
      'enchantment',
    ]) {
      const ids = Array.isArray(contentIds[kind]) ? contentIds[kind] : [];

      customIdsByKind.set(
        kind,
        new Set(ids.map((id) => String(id)))
      );
    }

    rebuildAssetReplacements();
    ensureCustomContentObserver();
    refreshCustomContent(document);
  }

  function isCustomContent(kind, id) {
    return customIdsByKind.get(kind)?.has(String(id)) ?? false;
  }

  function isCustomCard(id) {
    return isCustomContent('card', id);
  }

  function isCustomArtifact(id) {
    return isCustomContent('artifact', id);
  }

  /* Custom content rendering */

  let assetReplacements = new Map();
  let customContentObserver = null;

  function absoluteUrl(value) {
    if (typeof value !== 'string') {
      return null;
    }

    try {
      return new URL(value, location.href).href;
    } catch {
      return null;
    }
  }

  function localContentUrl(value) {
    if (typeof value !== 'string') {
      return null;
    }

    try {
      return new URL(value, `${DELTACARDS_BASE_URL}/`).href;
    } catch {
      return null;
    }
  }

  function replacementAssetUrl(assetUrl, fallbackPath) {
    const localUrl = localContentUrl(assetUrl);

    if (localUrl !== null) {
      const parsedLocalUrl = new URL(localUrl);

      if (
        parsedLocalUrl.origin === new URL(DELTACARDS_BASE_URL).origin
        && parsedLocalUrl.pathname.startsWith('/content-assets/')
      ) return parsedLocalUrl.href;
    }

    // Existing frontend assets belong to the page's origin, not localhost.
    return absoluteUrl(assetUrl) || fallbackPath;
  }

  function registerAssetReplacement(source, replacement) {
    const sourceUrl = absoluteUrl(source);
    const replacementUrl = absoluteUrl(replacement);

    if (
      sourceUrl === null
      || replacementUrl === null
      || sourceUrl === replacementUrl
    ) return;

    assetReplacements.set(sourceUrl, replacementUrl);
  }

  function rebuildAssetReplacements() {
    assetReplacements = new Map();

    for (const card of customContent.cards) {
      if (!card.imageUrl) continue;

      registerAssetReplacement(
        `/images/cards/${card.image}.png`,
        replacementAssetUrl(
          card.imageUrl,
          `/images/cards/${card.image}.png`
        )
      );

      registerAssetReplacement(
        `/images/cards/${card.baseImage}.png`,
        replacementAssetUrl(
          card.baseImageUrl || card.imageUrl,
          `/images/cards/${card.baseImage}.png`
        )
      );
    }

    for (const artifact of customContent.artifacts) {
      if (!artifact.imageUrl) continue;

      registerAssetReplacement(
        `/images/artifacts/${artifact.image}.png`,
        replacementAssetUrl(
          artifact.imageUrl,
          `/images/artifacts/${artifact.image}.png`
        )
      );

      registerAssetReplacement(
        `/images/artifacts/overlays/${artifact.image}.png`,
        replacementAssetUrl(
          artifact.imageUrl,
          `/images/artifacts/overlays/${artifact.image}.png`
        )
      );
    }

    for (
      const enchantment
      of customContent.enchantments
    ) {
      const assetName = enchantment.assetName || enchantment.name;

      registerAssetReplacement(
        `/images/enchants/backgrounds/${enchantment.name}.png`,
        replacementAssetUrl(
          enchantment.backgroundUrl,
          `/images/enchants/backgrounds/${assetName}.png`
        )
      );

      registerAssetReplacement(
        `/images/enchants/overlays/${enchantment.name}.png`,
        replacementAssetUrl(
          enchantment.overlayUrl,
          `/images/enchants/overlays/${assetName}.png`
        )
      );

      registerAssetReplacement(
        `/images/enchants/logs/${enchantment.name}.png`,
        replacementAssetUrl(
          enchantment.logUrl,
          `/images/enchants/logs/${assetName}.png`
        )
      );
    }

    for (const soul of customContent.souls) {
      const assetName = soul.assetName || soul.name;

      registerAssetReplacement(
        `/images/souls/${soul.name}.png`,
        replacementAssetUrl(
          soul.imageUrl,
          `/images/souls/${assetName}.png`
        )
      );
    }
  }

  function replaceAssetUrl(value) {
    const normalized = absoluteUrl(value);
    if (normalized === null) return value;

    return assetReplacements.get(normalized) || value;
  }

  function replaceCssUrls(value) {
    if (
      typeof value !== 'string'
      || (
        value.indexOf('url(') === -1
        && value.indexOf('URL(') === -1
      )
    ) return value;

    return value.replace(
      /url\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*?))\s*\)/gi,
      function (
        fullMatch,
        doubleQuoted,
        singleQuoted,
        unquoted
      ) {
        const rawUrl = (
          doubleQuoted
          ?? singleQuoted
          ?? unquoted
        ).trim();

        const replacement = replaceAssetUrl(rawUrl);
        if (replacement === rawUrl) return fullMatch;

        return `url("${replacement}")`;
      }
    );
  }

  function replaceHtmlAssetUrls(markup) {
    if (
      typeof markup !== 'string'
      || !markup.includes('images/')
    ) {
      return markup;
    }

    return markup.replace(
      /(\bsrc\s*=\s*)(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/gi,
      (
        fullMatch,
        prefix,
        doubleQuoted,
        singleQuoted,
        unquoted
      ) => {
        const source = doubleQuoted ?? singleQuoted ?? unquoted;

        const replacement = replaceAssetUrl(source);
        if (replacement === source) return fullMatch;

        return `${prefix}"${replacement}"`;
      }
    );
  }

  function elementsInRoot(root, selector) {
    const elements = [];

    if (
      root instanceof Element
      && root.matches(selector)
    ) {
      elements.push(root);
    }

    if (typeof root.querySelectorAll === 'function') {
      elements.push(
        ...root.querySelectorAll(selector)
      );
    }

    return elements;
  }

  function refreshAssetReference(element) {
    if (!(element instanceof Element)) {
      return;
    }

    if (element.matches('img[src]')) {
      const source = element.getAttribute('src');
      const replacement = replaceAssetUrl(source);

      if (replacement !== source) {
        element.setAttribute('src', replacement);
      }
    }

    if (element.hasAttribute('style')) {
      const source = element.getAttribute('style');
      const replacement = replaceCssUrls(source);

      if (replacement !== source) {
        element.setAttribute('style', replacement);
      }
    }
  }

  function refreshAssetReferences(root) {
    for (
      const element
      of elementsInRoot(root, 'img[src], [style]')
    ) {
      refreshAssetReference(element);
    }
  }

  function refreshCustomCardTranslations(root) {
    if (
      typeof window.jQuery !== 'function'
      || typeof window.jQuery.i18n !== 'function'
    ) return;

    const $ = window.jQuery;

    for (const card of customContent.cards) {
      const cardId = Number(card.fixedId ?? card.id);

      for (
        const element
        of elementsInRoot(root, `.card-${cardId}`)
      ) {
        const nameElement = element.querySelector('.cardName div');
        const descriptionElement = element.querySelector('.cardDesc div');

        if (nameElement !== null) {
          const name = $.i18n(`card-name-${cardId}`, 1);

          if (nameElement.innerHTML !== name) {
            nameElement.innerHTML = name;
          }
        }

        if (descriptionElement !== null) {
          const description = $.i18n(`card-${cardId}`);

          if (descriptionElement.innerHTML !== description) {
            descriptionElement.innerHTML = description;
          }
        }
      }
    }
  }

  function refreshCustomContent(root) {
    refreshAssetReferences(root);
    refreshCustomCardTranslations(root);
  }

  function ensureCustomContentObserver() {
    if (
      customContentObserver !== null
      || document.documentElement === null
    ) return;

    customContentObserver = new MutationObserver(
      (records) => {
        for (const record of records) {
          if (record.type === 'attributes') {
            refreshAssetReference(record.target);
            continue;
          }

          for (const node of record.addedNodes) {
            if (node.nodeType !== Node.ELEMENT_NODE) continue;
            refreshCustomContent(node);
          }
        }
      }
    );

    customContentObserver.observe(
      document.documentElement,
      {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['src'], // 'style' is handled by installJQueryAssetWriteHooks()
      }
    );
  }

  function installJQueryAssetWriteHooks() {
    const deadline = Date.now() + 10_000;

    function tryInstall() {
      const $ = window.jQuery;

      if (
        !$ ||
        typeof $.style !== 'function' ||
        typeof $.attr !== 'function'
      ) {
        if (Date.now() < deadline) {
          setTimeout(tryInstall, 10);
        }
        return;
      }

      const originalStyle = $.style;

      $.style = function () {
        const args = Array.from(arguments);
        const property = String(args[1] ?? '');

        if (
            args.length >= 3
            && typeof args[2] === 'string'
            && (
                property === 'background'
                || property === 'backgroundImage'
                || property === 'background-image'
            )
        ) {
          args[2] = replaceCssUrls(args[2]);
        }

        return Reflect.apply(originalStyle, this, args);
      };

      const originalAttr = $.attr;

      $.attr = function () {
        const args = Array.from(arguments);
        const attribute = String(args[1] ?? '').toLowerCase();

        if (typeof args[2] === 'string') {
          if (attribute === 'src') {
            args[2] = replaceAssetUrl(args[2]);
          } else if (attribute === 'style') {
            args[2] = replaceCssUrls(args[2]);
          }
        }

        return Reflect.apply(originalAttr, this, args);
      };

      /*
       * jQuery uses htmlPrefilter before parsing HTML strings for html(),
       * append(), prepend(), and similar APIs.
       */
      if (typeof $.htmlPrefilter === 'function') {
        const originalHtmlPrefilter = $.htmlPrefilter;

        $.htmlPrefilter = function (html) {
          return originalHtmlPrefilter.call(this, replaceHtmlAssetUrls(html));
        };
      }
    }

    tryInstall();
  }

  /* HTTP rewrites */

  function localHttpUrl(path) {
    return new URL(path, `${DELTACARDS_BASE_URL}/`);
  }

  function classifyRequest(method, rawUrl) {
    const sourceUrl = new URL(rawUrl, location.href);

    if (sourceUrl.origin !== location.origin) {
      return {
        kind: null,
        url: rawUrl,
      };
    }

    if (
      method === 'GET'
      && sourceUrl.pathname === '/Version'
      && sourceUrl.searchParams.get('type') === 'cards'
    ) {
      const localUrl = localHttpUrl('/cards-version/');
      localUrl.searchParams.set('type', 'cards');

      return {
        kind: 'cards-version',
        url: localUrl.href,
      };
    }

    if (
      method === 'GET'
      && sourceUrl.pathname === '/AllCards'
    ) {
      return {
        kind: 'cards',
        url: localHttpUrl('/cards/').href,
      };
    }

    if (sourceUrl.pathname === '/DecksConfig') {
      return {
        kind: 'decks-config',
        url: rawUrl,
      };
    }

    return {
      kind: null,
      url: rawUrl,
    };
  }

  function appendUniqueById(target, additions) {
    const ids = new Set(
      target.map((entry) => Number(entry.id))
    );

    for (const addition of additions) {
      const id = Number(addition.id);

      if (ids.has(id)) continue;

      ids.add(id);
      target.push({...addition});
    }
  }

  function transformDecksConfig(data) {
    const collection = JSON.parse(data.collection);
    const artifacts = JSON.parse(data.artifacts);
    const allArtifacts = JSON.parse(data.allArtifacts);

    const customCollection = (
      customContent.cards
        .filter((card) => card.rarity !== 'TOKEN')
        .map((card) => ({
          ...card,
          shiny: false,
          quantity: 25,
        }))
    );

    appendUniqueById(collection, customCollection);
    appendUniqueById(artifacts, customContent.artifacts);
    appendUniqueById(allArtifacts, customContent.artifacts);

    return {
      ...data,
      collection: JSON.stringify(collection),
      artifacts: JSON.stringify(artifacts),
      allArtifacts: JSON.stringify(allArtifacts),
    };
  }

  function customDeckActionUrl(body) {
    if (!body || typeof body !== 'object') return null;

    const action = body.action;

    if (
      (
        action === 'addCard'
        || action === 'removeCard'
      )
      && isCustomCard(body.idCard)
    ) {
      const url = localHttpUrl('/decks-config/');

      url.searchParams.set('action', action);
      url.searchParams.set('idCard', String(body.idCard));
      url.searchParams.set('isShiny', String(Boolean(body.isShiny)));
      url.searchParams.set('soul', String(body.soul));

      return url.href;
    }

    if (
      action === 'addArtifact'
      && isCustomArtifact(body.idArtifact)
    ) {
      const url = localHttpUrl('/decks-config/');

      url.searchParams.set('action', action);
      url.searchParams.set('idArtifact', String(body.idArtifact));
      url.searchParams.set('soul', String(body.soul));

      return url.href;
    }

    return null;
  }

  function installXhrInterception() {
    const OriginalXMLHttpRequest = window.XMLHttpRequest;

    const originalXhrOpen = OriginalXMLHttpRequest.prototype.open;
    const originalXhrSend = OriginalXMLHttpRequest.prototype.send;
    const originalXhrSetRequestHeader = OriginalXMLHttpRequest.prototype.setRequestHeader;

    const xhrMetadata = new WeakMap();

    OriginalXMLHttpRequest.prototype.open = function (method, url) {
      const args = Array.from(arguments);
      const normalizedMethod = String(method).toUpperCase();
      const route = classifyRequest(normalizedMethod, url);
      const asyncValue = args.length >= 3 ? args[2] : true;

      xhrMetadata.set(this, {
        kind: route.kind,
        originalMethod: normalizedMethod,
        async: asyncValue,

        // These requests are immediately rewritten to local GET endpoints.
        dropAuthorRequestHeaders: (
          route.kind === 'cards-version'
          || route.kind === 'cards'
        ),

        // DecksConfig POSTs might later be rewritten to a local GET, so hold
        // their headers until send() determines which request is being made.
        deferredHeaders: (
          route.kind === 'decks-config'
          && normalizedMethod === 'POST'
        ) ? [] : null,
      });

      args[1] = route.url;
      return Reflect.apply(originalXhrOpen, this, args);
    };

    OriginalXMLHttpRequest.prototype.setRequestHeader =
      function (name, value) {
        const metadata = xhrMetadata.get(this);

        if (metadata?.dropAuthorRequestHeaders) return;

        if (metadata?.deferredHeaders) {
          metadata.deferredHeaders.push([name, value]);
          return;
        }

        return originalXhrSetRequestHeader.call(this, name, value);
      };

      function applyDeferredHeaders(xhr, metadata) {
        const headers = metadata?.deferredHeaders;

        if (!headers) return;

        metadata.deferredHeaders = null;

        for (const [name, value] of headers) {
          originalXhrSetRequestHeader.call(xhr, name, value);
        }
      }

    OriginalXMLHttpRequest.prototype.send =
      function (body) {
        const metadata = xhrMetadata.get(this);

        if (
          metadata
          && metadata.kind === 'decks-config'
          && metadata.originalMethod === 'POST'
          && typeof body === 'string'
        ) {
          let parsedBody = null;

          try {
            parsedBody = JSON.parse(body);
          } catch {}

          const localUrl = customDeckActionUrl(parsedBody);

          if (localUrl !== null) {
            const timeout = this.timeout;
            const responseType = this.responseType;

            metadata.deferredHeaders = null;

            originalXhrOpen.call(
              this,
              'GET',
              localUrl,
              metadata.async
            );

            this.timeout = timeout;
            this.withCredentials = false;

            if (responseType) this.responseType = responseType;

            return originalXhrSend.call(this,null);
          }
        }

        // This was not a rewritten local request, so preserve its headers.
        applyDeferredHeaders(this, metadata);

        return originalXhrSend.call(this, body);
      };

    function transformResponseObject(xhr, value) {
      const metadata = xhrMetadata.get(xhr);

      if (
        !metadata
        || xhr.readyState !== 4
        || value === null
        || typeof value !== 'object'
      ) return value;

      if (metadata.kind === 'cards-version') {
        setCustomContent(value.customContent);
        return value;
      }

      if (
        metadata.kind === 'decks-config'
        && metadata.originalMethod === 'GET'
      ) return transformDecksConfig(value);

      return value;
    }

    function transformResponseText(xhr, value) {
      const metadata = xhrMetadata.get(xhr);

      if (
        !metadata
        || xhr.readyState !== 4
        || typeof value !== 'string'
      ) return value;

      if (
        metadata.originalText === value
        && metadata.transformedText !== undefined
      ) return metadata.transformedText;

      const isDecksConfigGet = (
        metadata.kind === 'decks-config'
        && metadata.originalMethod === 'GET'
      );

      if (metadata.kind !== 'cards-version' && !isDecksConfigGet) {
        return value;
      }

      let parsed;

      try {
        parsed = JSON.parse(value);
      } catch {
        return value;
      }

      metadata.originalText = value;
      metadata.transformedText = JSON.stringify(
        transformResponseObject(xhr, parsed)
      );

      return metadata.transformedText;
    }

    function patchXhrGetter(propertyName, transform) {
      const descriptor = Object.getOwnPropertyDescriptor(
        OriginalXMLHttpRequest.prototype,
        propertyName
      );

      if (
        !descriptor
        || typeof descriptor.get !== 'function'
        || !descriptor.configurable
      ) throw new Error(`Cannot intercept XMLHttpRequest.${propertyName}.`);

      Object.defineProperty(
        OriginalXMLHttpRequest.prototype,
        propertyName,
        {
          ...descriptor,
          get() {
            return transform(this, descriptor.get.call(this));
          },
        }
      );
    }

    patchXhrGetter('responseText', transformResponseText);

    patchXhrGetter(
      'response',
      (xhr, value) => {
        if (typeof value === 'string') {
          return transformResponseText(xhr, value);
        }

        return transformResponseObject(xhr, value);
      }
    );
  }

  function bufferWebSocketMessagesUntil(socket, readyPromise) {
    let released = false;
    let onmessage = null;
    let proxy = null;
    const queuedMessages = [];

    /*
     * Keep the native socket's message handler under bridge control.
     * game.js will assign socketGame.onmessage; the Proxy stores that handler
     * in `onmessage` instead of replacing this native handler.
     */
    socket.onmessage = function (event) {
      if (!released) {
        queuedMessages.push(event);
        return;
      }

      if (typeof onmessage === 'function') {
        onmessage.call(proxy, event);
      }
    };

    Promise.resolve(readyPromise).then(() => {
      released = true;

      for (const event of queuedMessages.splice(0)) {
        if (typeof onmessage === 'function') {
          onmessage.call(proxy, event);
        }
      }
    });

    proxy = new Proxy(socket, {
      get(target, property) {
        if (property === 'onmessage') {
          return onmessage;
        }

        /*
         * Native WebSocket getters and methods require the real WebSocket as
         * their receiver, not the Proxy.
         */
        const value = Reflect.get(target, property, target);

        return typeof value === 'function'
          ? value.bind(target)
          : value;
      },

      set(target, property, value) {
        if (property === 'onmessage') {
          onmessage = value;
          return true;
        }

        return Reflect.set(target, property, value, target);
      }
    });

    return proxy;
  }

  const OriginalWebSocket = window.WebSocket;

  function installWebsocketInterception() {
    window.WebSocket = new Proxy(OriginalWebSocket, {
      construct(target, args, newTarget) {
        const wsUrlArgs = args.slice();
        const wsUrl = new URL(wsUrlArgs[0], location.href);

        let redirect = false;

        if (wsUrl.pathname === '/game' && normalizedPathname() === '/Spectate') {
          const localGameID = getLocalGameID();

          if (localGameID !== null) {
            const localUrl = new URL(
              `/game/${localGameID}`,
              `${DELTACARDS_BASE_WEBSOCKET_URL}/`
            );

            localUrl.searchParams.set('player_id', '1');
            wsUrlArgs[0] = localUrl.href;
            redirect = true;
          }
        }

        const socket = Reflect.construct(target, wsUrlArgs, newTarget);
        if (redirect) {
          return bufferWebSocketMessagesUntil(socket, customTranslationsReady);
        }

        return socket;
      }
    });
  }

  /* Custom translations */

  async function fetchCustomTranslations(language) {
    const url = localHttpUrl('/translations/');
    url.searchParams.set('locale', language);

    const response = await fetch(
      url.href,
      {
        method: 'GET',
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error(`Custom translations returned HTTP ${response.status}.`);
    }

    return response.json();
  }

  async function applyCustomTranslations() {
    if (
      typeof window.jQuery !== 'function'
      || typeof window.jQuery.i18n !== 'function'
    ) return;

    const $ = window.jQuery;

    const locales = [
      ...new Set(['en', $.i18n().locale].filter(Boolean))
    ];

    const entries = await Promise.all(
      locales.map(async (locale) => [
        locale,
        await fetchCustomTranslations(locale),
      ])
    );

    await $.i18n().load(
      Object.fromEntries(entries)
    );

    $('body').i18n();

    if (typeof window.translateElement === 'function') {
      $([
        '[data-i18n-custom]',
        '[data-i18n-value]',
        '[data-i18n-title]',
        '[data-i18n-placeholder]',
      ].join(',')).each(function () {
        window.translateElement($(this));
      });
    }

    refreshCustomCardTranslations(document);
  }

  let translationApplicationQueue = Promise.resolve();

  function queueCustomTranslationApplication() {
    translationApplicationQueue = translationApplicationQueue
      .then(() => applyCustomTranslations())
      .catch((error) => {
        console.error(
          `${PLUGIN_NAME}: Could not apply custom translations.`,
          error
        );
      })
      .then(() => {
        // Allow the game to load even if custom translation loading failed.
        resolveCustomTranslationsReady();
      });

    return translationApplicationQueue;
  }

  /* Set up interception and hooks */

  if (interceptionEnabled) {
    installXhrInterception();
    installWebsocketInterception();

    // This isn't required, but it prevents spamming game's servers with invalid asset requests.
    installJQueryAssetWriteHooks();

    // Reapply after every normal translation load.
    document.addEventListener('translationReady', queueCustomTranslationApplication);

    if (window.translationReady === true) {
      queueCustomTranslationApplication();
    }

    console.info(`${PLUGIN_NAME}: Set up interception and hooks`);
  }

  /* UnderScript Plugin */

  function sleep(ms = 0) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function waitForUnderScript() {
    const deadline = Date.now() + 10 * 1000;

    while (Date.now() < deadline) {
      try {
        if (underscript && (typeof underscript.plugin === 'function')) {
          return;
        }

        await sleep(100);
      } catch {
        await sleep(100);
      }
    }

    throw new Error("UnderScript API was not available.");
  }

  async function initPlugin() {
    await waitForUnderScript();

    const plugin = underscript.plugin(PLUGIN_NAME);
    const settings = plugin.settings();

    settings.add({
      key: 'loadCustomContent',
      name: "Load custom content",
      type: 'boolean',
      default: SETTING_DEFAULTS.loadCustomContent,
    });

    settings.add({
      key: 'loadCustomContentEverywhere',
      name: "Load custom content everywhere except in online games",
      note: "Experimental. Use with caution.",
      type: 'boolean',
      default: SETTING_DEFAULTS.loadCustomContentEverywhere,
    });

    class StartButtonSetting extends underscript.utils.SettingType {
      constructor(name = 'startButton') {
        super(name);
      }

      value(value) {
        return value;
      }

      encode(value) {
        return value;
      }

      default() {
        return undefined;
      }

      element(value, update) {
        return $('<button>', {
          type: 'button',
          class: "btn btn-primary",
          text: "Start",
        }).on('click', () => update('start'));
      }

      labelFirst() {
        return null;
      }
    }

    settings.addType(new StartButtonSetting());

    const startLocalGame = settings.add({
      key: 'startLocalGame',
      name: "",
      type: `${plugin.name}:startButton`,
      category: "Local game",
      export: false,

      onChange: (action => {
        if (action !== 'start') return;
        startLocalGame.set(undefined);

        checkStatus()
          .then(() => {
            const gameID = Math.floor(Math.random() * 1_000_000_000) + 1;

            location.assign(`/Spectate?deltacardsGameId=${gameID}`);
          })
          .catch(() => {
            alert("Failed to connect to the local server. Is it offline?");
          });
      }),
    });

    console.info(`${PLUGIN_NAME}: Loaded`);
  }

  initPlugin().catch((error) => {
    console.error(`${PLUGIN_NAME}: Failed to load`, error);
  });

  /* Public API */

  window.deltacardsBridge = {
    isCustomContent,
    isCustomCard,
    isCustomArtifact,
    interceptionEnabled,
  };
})();
