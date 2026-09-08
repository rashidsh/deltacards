// ==UserScript==
// @name         deltacards Bridge
// @version      0.3.0
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

  const DEFAULT_PUBLIC_SERVER_BASE_URL = 'https://dc.rashidsh.ru';

  const SERVER_MODE_LOCAL = 'Local server';
  const SERVER_MODE_PUBLIC = 'Public server';

  const SETTINGS_PREFIX = `underscript.plugin.${PLUGIN_NAME}.`;
  const CUSTOM_LAUNCH_STORAGE_KEY = 'deltacardsBridge.customLaunch';
  const BROWSER_CONTENT_PREVIEW_STORAGE_KEY = 'deltacardsBridge.browserContentPreview';

  const SETTING_DEFAULTS = {
    serverMode: SERVER_MODE_LOCAL,
    serverPort: 8080,
    loadCustomContent: true,
    loadCustomContentEverywhere: false,
  };

  let deltacardsPort = readPortSetting('serverPort', SETTING_DEFAULTS.serverPort);
  let deltacardsServerMode = normalizedServerMode(
    readStringSetting('serverMode', SETTING_DEFAULTS.serverMode)
  );

  function configuredServerBaseUrl() {
    if (deltacardsServerMode === SERVER_MODE_PUBLIC) {
      return DEFAULT_PUBLIC_SERVER_BASE_URL;
    }

    return `http://localhost:${deltacardsPort}`;
  }

  function serverHttpUrl(path) {
    return new URL(path, `${configuredServerBaseUrl()}/`);
  }

  function serverWebSocketUrl(path) {
    const url = serverHttpUrl(path);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return url;
  }

  /* Helper functions */

  function normalizedPort(value, defaultValue) {
    const port = Number(value);

    if (
      !Number.isInteger(port)
      || port < 1
      || port > 65_535
    ) return defaultValue;

    return port;
  }

  function normalizedServerMode(value) {
    return value === SERVER_MODE_PUBLIC
      ? SERVER_MODE_PUBLIC
      : SERVER_MODE_LOCAL;
  }

  async function checkStatus() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);

    try {
      const response = await fetch(serverHttpUrl('/check/').href, {
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

  function readStringSetting(key, defaultValue) {
    const rawValue = localStorage.getItem(SETTINGS_PREFIX + key);

    if (rawValue === null) return defaultValue;

    return rawValue;
  }

  function readPortSetting(key, defaultValue) {
    const rawValue = localStorage.getItem(SETTINGS_PREFIX + key);

    if (rawValue === null) return defaultValue;

    return normalizedPort(rawValue, defaultValue);
  }

  function readBrowserContentPreview() {
    try {
      const preview = JSON.parse(
        localStorage.getItem(BROWSER_CONTENT_PREVIEW_STORAGE_KEY)
      );

      if (!preview || preview.previewVersion !== 1) return null;

      return preview;
    } catch {
      return null;
    }
  }

  function normalizedPathname() {
    const pathname = location.pathname;

    if (pathname.length > 1) {
      return pathname.replace(/\/+$/, '');
    }

    return pathname;
  }

  function readActiveCustomLaunch() {
    if (normalizedPathname() !== '/Spectate') return null;

    let value;

    try {
      value = JSON.parse(sessionStorage.getItem(CUSTOM_LAUNCH_STORAGE_KEY));
    } catch {
      return null;
    }

    if (!value) return null;

    const gameID = String(value.gameId ?? '');
    const pageGameID = new URL(location.href).searchParams.get('deltacardsGameId');
    const playerToken = value.playerToken;

    if (
      gameID.length === 0
      || gameID !== pageGameID
    ) return null;

    return {
      gameId: gameID,
      playerToken,
    };
  }

  const activeCustomLaunch = readActiveCustomLaunch();

  let activeBrowserContentPreview = null;

  let cardsVersionWasTransformed = false;

  function getLocalGameID() {
    if (normalizedPathname() !== '/Spectate') {
      return null;
    }

    return new URL(location.href).searchParams.get('deltacardsGameId');
  }

  function isInLocalGame() {
    return (
      normalizedPathname() === '/Spectate'
      && getLocalGameID() !== null
    );
  }

  function shouldEnableInterception() {
    if (activeCustomLaunch !== null) return true;

    const loadCustomContent = readBooleanSetting(
      'loadCustomContent',
      SETTING_DEFAULTS.loadCustomContent
    );
    if (!loadCustomContent) return false;

    const loadCustomContentEverywhere = readBooleanSetting(
      'loadCustomContentEverywhere',
      SETTING_DEFAULTS.loadCustomContentEverywhere
    );

    if (loadCustomContentEverywhere) {
      return normalizedPathname() !== '/Game';
    }

    return isInLocalGame();
  }

  const interceptionEnabled = shouldEnableInterception();

  let contentEditor = null;
  let contentEditorPromise = null;

  function createContentEditor(factory) {
    return factory.create({
      httpUrl(path) {
        return serverHttpUrl(path).href;
      },
      getDeck() {
        return readStringSetting('humanDeckCode', '').trim();
      },
      isCustomContentEverywhereEnabled() {
        return readBooleanSetting(
          'loadCustomContentEverywhere',
          SETTING_DEFAULTS.loadCustomContentEverywhere
        );
      },
      onLaunch(result) {
        sessionStorage.setItem(
          CUSTOM_LAUNCH_STORAGE_KEY,
          JSON.stringify({
            gameId: result.gameId,
            playerToken: result.playerToken,
          })
        );

        location.assign(`/Spectate?deltacardsGameId=${result.gameId}`);
      },
    });
  }

  function ensureContentEditor() {
    if (contentEditor !== null) {
      return Promise.resolve(contentEditor);
    }

    if (contentEditorPromise !== null) {
      return contentEditorPromise;
    }

    contentEditorPromise = Promise.resolve(window.deltacardsContentEditor)
      .then((factory) => {
        const editor = createContentEditor(factory);

        contentEditor = editor;
        return editor;
      })
      .catch((error) => {
        contentEditorPromise = null;
        throw error;
      });

    return contentEditorPromise;
  }

  async function openContentEditor() {
    try {
      const editor = await ensureContentEditor();
      await editor.open();
    } catch (error) {
      console.error(`${PLUGIN_NAME}: Could not load the content editor.`, error);
      alert(`Could not load the content editor: ${error.message}`);
    }
  }

  let resolveCustomTranslationsReady = () => {};

  const customTranslationsReady = interceptionEnabled
    ? new Promise((resolve) => {
        resolveCustomTranslationsReady = resolve;
      })
    : Promise.resolve();

  let resolveCustomContentReady = () => {};

  const customContentReady = interceptionEnabled
    ? new Promise((resolve) => {
        resolveCustomContentReady = resolve;
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
  let clientAssetUrls = new Map();

  function setCustomContent(value) {
    value = (
      value && typeof value === 'object'
    ) ? value : {};

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

    prepareCustomContentAssets(customContent)
      .then((assetUrls) => {
        clientAssetUrls = assetUrls;
        rebuildAssetReplacements();
        ensureCustomContentObserver();
        refreshCustomContent(document);
        resolveCustomContentReady();
      });
  }

  async function prepareCustomContentAssets(content) {
    const entries = [
      ...content.cards,
      ...content.artifacts,
      ...content.enchantments,
      ...content.souls,
    ];

    const assetIds = new Set(
      entries
        .map((entry) => entry.clientAssetId)
        .filter((assetId) => typeof assetId === 'string')
    );

    const assetUrls = new Map();

    if (assetIds.size === 0) {
      return assetUrls;
    }

    const editor = await ensureContentEditor();
    await editor.ready;

    await Promise.all([...assetIds].map(async (assetId) => {
      const url = await editor.assetUrl(assetId);
      if (url !== null) assetUrls.set(assetId, url);
    }));

    return assetUrls;
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

  // 1x1px placeholder image
  const MISSING_ASSET_URL = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';

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

  function serverContentUrl(value) {
    if (typeof value !== 'string') {
      return null;
    }

    try {
      return serverHttpUrl(value).href;
    } catch {
      return null;
    }
  }

  function replacementAssetUrl(assetUrl, fallbackPath) {
    const serverUrl = serverContentUrl(assetUrl);

    if (serverUrl !== null) {
      const parsedServerUrl = new URL(serverUrl);

      if (
        parsedServerUrl.origin === serverHttpUrl('/').origin
        && parsedServerUrl.pathname.startsWith('/content-assets/')
      ) return parsedServerUrl.href;
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

  function customAssetUrl(
    entry,
    serverField,
    fallbackPath
  ) {
    const clientAssetId = entry.clientAssetId;

    if (
      typeof clientAssetId === 'string'
      && clientAssetUrls.has(clientAssetId)
    ) {
      return clientAssetUrls.get(clientAssetId);
    }

    if (typeof entry[serverField] === 'string') {
      return replacementAssetUrl(
        entry[serverField],
        fallbackPath
      );
    }

    if (
      Object.prototype.hasOwnProperty.call(entry, 'clientAssetId')
    ) return MISSING_ASSET_URL;

    return null;
  }

  function rebuildAssetReplacements() {
    assetReplacements = new Map();

    for (const card of customContent.cards) {
      const imagePath = `/images/cards/${card.image}.png`;
      const imageUrl = customAssetUrl(
        card,
        'imageUrl',
        imagePath
      );
      if (imageUrl === null) continue;

      registerAssetReplacement(
        imagePath,
        imageUrl
      );

      const basePath = `/images/cards/${card.baseImage}.png`;
      registerAssetReplacement(
        basePath,
        customAssetUrl(
          {
            ...card,
            imageUrl: card.baseImageUrl || card.imageUrl,
          },
          'imageUrl',
          basePath
        ) || imageUrl
      );
    }

    for (const artifact of customContent.artifacts) {
      const imagePath = `/images/artifacts/${artifact.image}.png`;
      const imageUrl = customAssetUrl(
        artifact,
        'imageUrl',
        imagePath
      );
      if (imageUrl === null) continue;

      registerAssetReplacement(
        imagePath,
        imageUrl
      );

      registerAssetReplacement(
        `/images/artifacts/overlays/${artifact.image}.png`,
        imageUrl
      );
    }

    for (
      const enchantment
      of customContent.enchantments
    ) {
      const backgroundPath = `/images/enchants/backgrounds/${enchantment.name}.png`;
      const overlayPath = `/images/enchants/overlays/${enchantment.name}.png`;
      const logPath = `/images/enchants/logs/${enchantment.name}.png`;

      registerAssetReplacement(
        backgroundPath,
        customAssetUrl(
          enchantment,
          'backgroundUrl',
          backgroundPath
        ) || MISSING_ASSET_URL
      );

      registerAssetReplacement(
        overlayPath,
        replacementAssetUrl(
          enchantment.overlayUrl,
          overlayPath
        ) || MISSING_ASSET_URL
      );

      // TODO `backgroundUrl` is temporarily used for `logUrl`
      registerAssetReplacement(
        logPath,
        customAssetUrl(
          enchantment,
          'backgroundUrl',
          backgroundPath
        ) || MISSING_ASSET_URL
      );
    }

    for (const soul of customContent.souls) {
      const imagePath = `/images/souls/${soul.name}.png`;
      const imageUrl = customAssetUrl(
        soul,
        'imageUrl',
        imagePath
      );
      if (imageUrl === null) continue;

      registerAssetReplacement(
        imagePath,
        imageUrl
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
      let localUrl;

      if (activeCustomLaunch !== null) {
        localUrl = serverHttpUrl(
          `/v1/games/${activeCustomLaunch.gameId}/cards-version`
        );
      } else {
        localUrl = serverHttpUrl('/cards-version/');
        localUrl.searchParams.set('type', 'cards');
      }

      return {
        kind: 'cards-version',
        url: localUrl.href,
        authorization: (
          activeCustomLaunch === null
            ? null
            : `Bearer ${activeCustomLaunch.playerToken}`
        ),
      };
    }

    if (
      method === 'GET'
      && sourceUrl.pathname === '/AllCards'
    ) {
      let localUrl;

      if (activeCustomLaunch !== null) {
        localUrl = serverHttpUrl(
          `/v1/games/${activeCustomLaunch.gameId}/cards`
        );
      } else {
        localUrl = serverHttpUrl('/cards/');
      }

      return {
        kind: 'cards',
        url: localUrl.href,
        authorization: (
          activeCustomLaunch === null
            ? null
            : `Bearer ${activeCustomLaunch.playerToken}`
        ),
      };
    }

    if (sourceUrl.pathname === '/DecksConfig') {
      return {
        kind: 'decks-config',
        url: rawUrl,
        authorization: null,
      };
    }

    return {
      kind: null,
      url: rawUrl,
      authorization: null,
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

  function previewForBaseVersion(cardsVersion) {
    if (activeCustomLaunch !== null) return null;

    const preview = readBrowserContentPreview();

    return (
      preview?.baseCardsVersion === cardsVersion
        ? preview
        : null
    );
  }

  function transformCardsVersionResponse(data) {
    cardsVersionWasTransformed = true;

    const preview = previewForBaseVersion(
      data.cardsVersion
    );
    const result = {
      ...data,
    };

    if (preview !== null) {
      activeBrowserContentPreview = preview;
      result.cardsVersion = preview.cardsVersion;
      result.customContent = preview.customContent;
    } else {
      activeBrowserContentPreview = null;
    }

    setCustomContent(result.customContent);

    if (
      activeBrowserContentPreview !== null
      && window.translationReady === true
    ) {
      queueCustomTranslationApplication();
    }

    return result;
  }

  function transformCardsResponse(data) {
    if (activeBrowserContentPreview === null) {
      return data;
    }

    const cards = JSON.parse(data.cards);

    appendUniqueById(
      cards,
      activeBrowserContentPreview.customContent.cards || []
    );

    return {
      ...data,
      cards: JSON.stringify(cards),
    };
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

    const customArtifacts = customContent.artifacts.filter(
      (artifact) => artifact.rarity !== 'TOKEN'
    );

    appendUniqueById(collection, customCollection);
    appendUniqueById(artifacts, customArtifacts);
    appendUniqueById(allArtifacts, customArtifacts);

    return {
      ...data,
      collection: JSON.stringify(collection),
      artifacts: JSON.stringify(artifacts),
      allArtifacts: JSON.stringify(allArtifacts),
    };
  }

  function localDeckActionResponse(body) {
    if (!body || typeof body !== 'object') return null;

    if (
      body.action === 'addCard'
      || body.action === 'removeCard'
    ) {
      const card = customContent.cards.find(
        (entry) => Number(entry.id) === Number(body.idCard)
      );

      if (!card) return null;

      return {
        soul: String(body.soul),
        card: JSON.stringify({
          ...card,
          shiny: Boolean(body.isShiny),
        }),
      };
    }

    if (body.action === 'addArtifact') {
      const artifact = customContent.artifacts.find(
        (entry) => (
          Number(entry.id) === Number(body.idArtifact)
        )
      );

      if (!artifact) return null;

      return {
        action: 'getArtifactAdded',
        soul: String(body.soul),
        artifact: JSON.stringify(artifact),
      };
    }

    return null;
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
      const url = serverHttpUrl('/decks-config/');

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
      const url = serverHttpUrl('/decks-config/');

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
      const result = Reflect.apply(originalXhrOpen, this, args);

      if (typeof route.authorization === 'string') {
        originalXhrSetRequestHeader.call(
          this,
          'Authorization',
          route.authorization
        );
      }

      return result;
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
            metadata.localDeckAction = parsedBody;

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

      if (metadata.localDeckAction) {
        return localDeckActionResponse(metadata.localDeckAction) || value;
      }

      if (metadata.kind === 'cards-version') {
        return transformCardsVersionResponse(value);
      }

      if (metadata.kind === 'cards') {
        return transformCardsResponse(value);
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

      const isLocalDeckAction = Boolean(metadata.localDeckAction);
      const isDecksConfigGet = (
        metadata.kind === 'decks-config'
        && metadata.originalMethod === 'GET'
      );

      if (
        metadata.kind !== 'cards-version'
        && metadata.kind !== 'cards'
        && !isDecksConfigGet
        && !isLocalDeckAction
      ) {
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

  let activeCustomGameSocket = null;

  function sendCustomGameCommand(action) {
    if (
      activeCustomGameSocket === null
      || activeCustomGameSocket.readyState !== OriginalWebSocket.OPEN
    ) return;

    activeCustomGameSocket.send(
      JSON.stringify({action})
    );
  }

  function installWebsocketInterception() {
    window.WebSocket = new Proxy(OriginalWebSocket, {
      construct(target, args, newTarget) {
        const wsUrlArgs = args.slice();
        const wsUrl = new URL(wsUrlArgs[0], location.href);

        let redirect = false;

        if (wsUrl.pathname === '/game' && normalizedPathname() === '/Spectate') {
          const localGameID = getLocalGameID();

          if (localGameID !== null) {
            let targetUrl = null;

            if (activeCustomLaunch !== null) {
              targetUrl = serverWebSocketUrl(
                `/v1/games/${activeCustomLaunch.gameId}/ws`
              );
              targetUrl.searchParams.set(
                'player_token',
                activeCustomLaunch.playerToken
              );
            } else if (
              deltacardsServerMode === SERVER_MODE_LOCAL
            ) {
              targetUrl = serverWebSocketUrl(
                `/game/${localGameID}`
              );
              targetUrl.searchParams.set('player_id', '1');

              const humanDeck = readStringSetting('humanDeckCode', '').trim();
              if (humanDeck) {
                targetUrl.searchParams.set('human_deck', humanDeck);
              }

              const botDeck = readStringSetting('botDeckCode', '').trim();
              if (botDeck) {
                targetUrl.searchParams.set('bot_deck', botDeck);
              }
            }

            if (targetUrl !== null) {
              wsUrlArgs[0] = targetUrl.href;
              redirect = true;
            }
          }
        }

        const socket = Reflect.construct(target, wsUrlArgs, newTarget);
        if (redirect) {
          activeCustomGameSocket = bufferWebSocketMessagesUntil(
            socket,
            Promise.all([
              customTranslationsReady,
              customContentReady,
            ])
          );

          socket.addEventListener('close', () => {
            activeCustomGameSocket = null;
          });

          if (!cardsVersionWasTransformed) {
            console.warn(
              `${PLUGIN_NAME}: failed to intercept some requests in time; retrying them now...`
            );
            window.initCards();
          }

          return activeCustomGameSocket;
        }

        return socket;
      }
    });
  }

  /* Custom translations */

  async function fetchCustomTranslations(language) {
    let url;

    if (activeCustomLaunch !== null) {
      url = serverHttpUrl(`/v1/games/${activeCustomLaunch.gameId}/translations`);
    } else {
      url = serverHttpUrl('/translations/');
    }

    url.searchParams.set('locale', language);

    const headers = {};
    if (activeCustomLaunch !== null) {
      headers.Authorization = `Bearer ${activeCustomLaunch.playerToken}`;
    }

    const response = await fetch(
      url.href,
      {
        method: 'GET',
        cache: 'no-store',
        headers,
      }
    );

    if (!response.ok) {
      throw new Error(`Custom translations returned HTTP ${response.status}.`);
    }

    const entries = await response.json();

    if (
      activeCustomLaunch === null
      && activeBrowserContentPreview !== null
    ) {
      Object.assign(entries, activeBrowserContentPreview.translations);
    }

    return entries;
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

  function addCustomGameControls(plugin) {
    const replayControls = $(`
      <tr id="replay_controls">
        <td class="leftPart"></td>
        <td class="centerPart"></td>
        <td class="rightPart" style="padding-top: 12px; padding-bottom: 8px">
          <button id="btn-deltacards-add-card" class="btn btn-sm btn-success">+Card</button>
          <button id="btn-deltacards-debug" class="btn btn-sm btn-primary">Debug</button>
        </td>
      </tr>
    `);

    replayControls
      .find('#btn-deltacards-add-card')
      .on('click', () => {
        sendCustomGameCommand('deltacardsAddCard');
      });

    replayControls
      .find('#btn-deltacards-debug')
      .on('click', () => {
        sendCustomGameCommand('deltacardsDebug');
      });

    // Layout fix
    $('.profile').last().children('tbody').children('tr').children('td').css('padding-top', '4px');
    plugin.addStyle('#yourAvatar{bottom: 52px} #game-history{height: 639px}');

    $('.profile').last().children('tbody').append(replayControls);
  }

  async function initPlugin() {
    await waitForUnderScript();

    const plugin = underscript.plugin(PLUGIN_NAME);
    const eventManager = plugin.events;
    const settings = plugin.settings();

    underscript.onPage('Spectate', () => {
      if (isInLocalGame()) {
        eventManager.once('allCardsReady', () => addCustomGameControls(plugin));
      }
    });

    settings.add({
      key: 'loadCustomContent',
      name: "Load custom content",
      type: 'boolean',
      default: SETTING_DEFAULTS.loadCustomContent,
    });

    settings.add({
      key: 'loadCustomContentEverywhere',
      name: "Load custom content everywhere except in online games",
      note: "Experimental. Turn this off first if you encounter any problems.",
      type: 'boolean',
      default: SETTING_DEFAULTS.loadCustomContentEverywhere,
    });

    class PortSetting extends underscript.utils.SettingType {
      constructor(name = 'port') {
        super(name);
      }

      value(value) {
        return value;
      }

      encode(value) {
        return value;
      }

      default() {
        return SETTING_DEFAULTS.serverPort;
      }

      element(value, update) {
        const $input = $('<input>', {
          type: 'number',
          class: 'form-control',
          min: 1,
          max: 65_535,
          step: 1,
          value: value,
        }).css({
          width: '100px',
          display: 'inline-block',
        }).on('change', function () {
          update(normalizedPort(this.value, 8080));
        });

        // make label centered
        requestAnimationFrame(() => {
          $input.parent().css('align-items', 'center');
        });

        return $input;
      }
    }

    settings.add({
      key: 'serverMode',
      name: "Game server",
      type: 'select',
      note: (
        'Local server: connect to your own deltacards server running locally.'
        + '<br><br>Public server: play without setting up a server yourself.'
        + '<br>Connect to a hosted deltacards server that is not affiliated with Undercards.'
        + '<br><br>Only the data needed to run the match is sent to the server, such as custom content and in-game actions.'
        + '<br>Custom images always stay in your browser.'
      ),
      category: "Custom games",
      default: SETTING_DEFAULTS.serverMode,
      options: [
        SERVER_MODE_LOCAL,
        SERVER_MODE_PUBLIC,
      ],
      onChange(value) {
        deltacardsServerMode = value;
      },
    });

    settings.addType(new PortSetting());

    settings.add({
      key: 'serverPort',
      name: "Local server port",
      type: `${plugin.name}:port`,
      note: "Used only when Game server is set to Local server.",
      category: "Custom games",
      default: SETTING_DEFAULTS.serverPort,
      onChange: (value => {
        deltacardsPort = normalizedPort(value, SETTING_DEFAULTS.serverPort);
      }),
    });

    settings.add({
      key: 'humanDeckCode',
      name: "Your deck code",
      note: "Base64 or JSON deck code. Leave empty for the server default.",
      type: 'text',
      category: "Custom games",
    });

    settings.add({
      key: 'botDeckCode',
      name: "Bot deck code",
      note: "Base64 or JSON deck code. Leave empty for the server default.",
      type: 'text',
      category: "Custom games",
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
      category: "Custom games",
      export: false,

      onChange: (action => {
        if (action !== 'start') return;
        startLocalGame.set(undefined);

        if (deltacardsServerMode === SERVER_MODE_PUBLIC) {
          alert("Public-server matches must be started through the Custom Content Editor.");
          return;
        }

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

    class EditorButtonSetting extends underscript.utils.SettingType {
      constructor(name = 'editorButton') {
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
          class: 'btn btn-primary',
          text: "Open Custom Content Editor",
        }).css({
          'margin-bottom': '8px',
        }).on('click', () => update('open'));
      }

      labelFirst() {
        return null;
      }
    }

    settings.addType(new EditorButtonSetting());

    const openEditor = settings.add({
      key: 'openContentEditor',
      name: '',
      type: `${plugin.name}:editorButton`,
      category: "Custom content",
      export: false,
      onChange(action) {
        if (action !== 'open') return;
        openEditor.set(undefined);

        void openContentEditor();
      },
    });

    function updateOpenContentEditorHotkey(key) {
      for (const boundKey of [...openContentEditorHotkey.keys]) {
        openContentEditorHotkey.unbindKey(boundKey);
      }

      if (typeof key === 'string' && key.length > 0) {
        openContentEditorHotkey.bindKey(key);
      }
    }

    const openContentEditorKeybind = settings.add({
      key: 'openContentEditorKeybind',
      name: "Open Custom Content Editor shortcut",
      type: 'keybind',
      default: 'F8',
      category: "Custom content",
      onChange: updateOpenContentEditorHotkey,
    });

    const openContentEditorHotkey = new underscript.utils.Hotkey(
      "Open Custom Content Editor",
      (event) => {
        const target = event.target;

        // Do not reopen the editor while it is already open.
        // Do not trigger the shortcut while the user is typing.
        if (
          document.querySelector('.dc-editor-overlay:not([hidden])') !== null
          || target instanceof HTMLInputElement
          || target instanceof HTMLSelectElement
          || target instanceof HTMLTextAreaElement
          || target?.isContentEditable
        ) return;

        event.preventDefault();
        void openContentEditor();
      }
    );

    updateOpenContentEditorHotkey(openContentEditorKeybind.value());
    plugin.hotkey.register(openContentEditorHotkey);

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

// bundled `content-editor.js`
(() => {
  'use strict';

  const DATABASE_NAME = 'deltacards-browser-content';
  const DATABASE_VERSION = 1;

  const CATALOG_PREVIEW_STORAGE_KEY = 'deltacardsBridge.browserContentPreview';

  const MAX_IMPORT_BYTES = 8 * 1024 * 1024;
  const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
  const EXTERNAL_EDITOR_ORIGIN = 'https://uc-editor.vercel.app/';

  const BLOCKLY_BASE_URL = 'https://unpkg.com/blockly@13.2.1';
  const BLOCKLY_PLUGIN_URLS = [
    'https://unpkg.com/@blockly/theme-dark/dist/index.js',
    'https://unpkg.com/@blockly/toolbox-search/dist/index.js',
  ];

  const UNDERCARDS_CARD_SCRIPT_URL = 'https://undercards.net/js/card.js';
  const UNDERCARDS_HELPER_SCRIPT_URL = 'https://undercards.net/js/helper.js';

  // Example custom content
  const INITIAL_EDITOR_BACKUP = {"backupVersion":1,"pack":{"schemaVersion":1,"packId":"4b94cae7-bbcc-448f-bad7-8d49632c516e","name":"Example Pack"},"editorEntities":[{"contentId":"bf2bec8a-94bf-43b9-b6e7-e8d5e43759f5","importKey":"artifact:example artifact","kind":"artifact","definition":{"name":"Example Artifact","description":"{{KW:TURN_START}}: Enchant the leftmost unenchanted ally board slot with Example Enchantment.","rarity":"COMMON","initialCounter":0,"image":{"source":"existing","name":"Gachapon"}},"implementation":{"irVersion":1,"variables":[],"targets":null,"need":null,"abilities":[{"nodeId":"qn(__@Mo%1b--gn5i]U$","ability":"turn_start","effect":{"nodeId":"[;}t?9;)+C;jtX#WRZ$P","node":"action.enchant","slot":{"nodeId":"v}?{V5+:AT|I4z?c/(=j","node":"selector.take","count":{"nodeId":"`8B3O7Eo|%VtO#+C(c36","node":"value.literal","value":1},"selector":{"nodeId":"XB_.}Mcjc0Oc%iTr`$9G","node":"selector.filter","selector":{"nodeId":")rYS}qDpb-d9_Z3|rmAq","node":"selector.board_slots_of","player":{"nodeId":"2%]?x=M?NKbI5D^PaWXZ","node":"selector.you"}},"predicate":{"nodeId":":i#Uco+d`O}0l9;w(~*a","node":"predicate.slot_state","state":"unenchanted"}},"side":"first"},"enchantment":{"nodeId":"[;}t?9;)+C;jtX#WRZ$P","node":"selector.enchantment_by_name","name":"Example Enchantment"}}}],"reactions":[]},"workspace":{"blocks":{"languageVersion":0,"blocks":[{"type":"dc_root_artifact","id":"ZUwFdo!KQf,z]f([x#wQ","x":20,"y":20,"deletable":false,"movable":false},{"type":"dc_ability","id":"qn(__@Mo%1b--gn5i]U$","x":200,"y":20,"fields":{"ABILITY":"turn_start"},"next":{"block":{"type":"dc_action_enchant","id":"[;}t?9;)+C;jtX#WRZ$P","fields":{"NAME":"Example Enchantment"},"inputs":{"SLOT":{"shadow":{"type":"dc_selector_random","id":"R$f:GeF_s1Fs9|Y:IF_g","inputs":{"COUNT":{"shadow":{"type":"dc_value_number","id":"Lk.n+Ongv+nD?LNx)lvu","fields":{"VALUE":1}}},"SELECTOR":{"shadow":{"type":"dc_selector_ally_slots","id":"Cr!QJ?XmO-o^[(guE,4W"}}}},"block":{"type":"dc_selector_take","id":"v}?{V5+:AT|I4z?c/(=j","fields":{"SIDE":"first"},"inputs":{"COUNT":{"block":{"type":"dc_value_number","id":"`8B3O7Eo|%VtO#+C(c36","fields":{"VALUE":1}}},"SELECTOR":{"block":{"type":"dc_selector_filter","id":"XB_.}Mcjc0Oc%iTr`$9G","inline":false,"inputs":{"SELECTOR":{"shadow":{"type":"dc_selector_ally_monsters","id":"5syl5h{DkMVAE@6K)aY6"},"block":{"type":"dc_selector_board_slots_of","id":")rYS}qDpb-d9_Z3|rmAq","inputs":{"PLAYER":{"shadow":{"type":"dc_selector_you","id":"Tfn7)F71O1b-I_Jqrn)]"},"block":{"type":"dc_selector_you","id":"2%]?x=M?NKbI5D^PaWXZ"}}}}},"PREDICATE":{"shadow":{"type":"dc_predicate_damaged","id":"f9y.`-kUt,,(^Z#Ts0nW"},"block":{"type":"dc_predicate_slot_state","id":":i#Uco+d`O}0l9;w(~*a","fields":{"STATE":"unenchanted"}}}}}}}}}}}}}]}},"workspaceValid":true,"import":{"adapter":"uc-editor","adapterVersion":1,"key":"artifact:example artifact"}},{"contentId":"b19a4554-bdbd-431a-ab63-c7b728e7a06b","importKey":"enchantment:7","kind":"enchantment","definition":{"name":"Example Enchantment","description":"After a monster is played here, look at 3 random monsters with less {{COST}} than it. Turn the monster into the chosen monster, and this effect expires.","initialCounter":0,"image":{"source":"client","assetId":"988b808a-5a9a-4484-8177-c15ad602f436"}},"implementation":{"irVersion":1,"variables":[],"targets":null,"need":null,"abilities":[],"reactions":[{"nodeId":"W*I[n}W/e|5WV/![k/f5","event":"monster_summoned","condition":{"nodeId":"lDbLq}w.mL]GzjYL+93C","node":"predicate.and","predicates":[{"nodeId":"}2#0As~2GKfob3t|+6]#","node":"value.event","field":"is_played"},{"nodeId":"5h;U7#Gq7`,dEe*v1LWu","node":"predicate.compare","left":{"nodeId":"H]PBdnOI.U6,n?1~l|mA","node":"value.attribute","selector":{"nodeId":"GVPJQU0Q-dg$4e59T}3/","node":"selector.slot_of","selector":{"nodeId":"Gbo/bzA:0R#2uAt`(j_U","node":"selector.event_entity","role":"monster"}},"attribute":"id"},"right":{"nodeId":"fH?1tTM-:lf9$3ynsQj~","node":"value.attribute","selector":{"nodeId":"Kf=df]0b|qob0Ohh)KvW","node":"selector.slot_of","selector":{"nodeId":"=h*mh`gL;39bSU,,r`$:","node":"selector.self"}},"attribute":"id"},"operator":"eq"}]},"effect":{"nodeId":"EddkS)fA/C9BG8y1RoQ(","node":"effect.then","effect":{"nodeId":"F=Lpk$^5^t!YD^+[@)A*","node":"action.choose","player":{"nodeId":".?y+wMZB05,[i7RKqnuV","node":"selector.you"},"options":{"nodeId":"*gkP/g`MId(e[;sZnM8E","node":"selector.discover","count":{"nodeId":"Z7]#{RVjsiFnG]#@3B?e","node":"value.literal","value":3},"controller":{"nodeId":"hWmYkK4DJX%1H+L83iN.","node":"selector.you"},"predicate":{"nodeId":"~S)Sb`pVt5?TI%-=NQsb","node":"predicate.and","predicates":[{"nodeId":"|fMx~2jTtza8IZf()H#^","node":"predicate.and","predicates":[{"nodeId":"hs`l%JyIAN|]iE^u40|L","node":"predicate.is_monster"},{"nodeId":"BdZGU5Q=vR[i]Q4Ism5[","node":"predicate.rarity","operator":"lt","rarity":"TOKEN"}]},{"nodeId":"^RA-*LHK]G?D]}:4njtP","node":"predicate.attribute_compare","value":{"nodeId":"fen,3)BOiIw]wt.^a}7+","node":"value.attribute","selector":{"nodeId":"l{}Jt2BBJXVoGw.G;G0s","node":"selector.event_snapshot","role":"monster"},"attribute":"cost"},"attribute":"cost","operator":"lt"}]}}},"then":{"nodeId":"_cwr+-lE6IdcLuaJU*je","node":"effect.sequence","effects":[{"nodeId":"_cwr+-lE6IdcLuaJU*je","node":"action.transform_card","target":{"nodeId":"C)7=f/tu:YnE`JJ@l)?l","node":"selector.event_entity","role":"monster"},"new_card":{"nodeId":"2Ob0Zzg=-9.{Y1#*flm!","node":"selector.choice_selected"}},{"nodeId":"?wa^3;6U-Jz~6u6nkzC{","node":"action.remove_enchantment","target":{"nodeId":"IdO531PzKI%N}e%-/;,k","node":"selector.self"}}]},"else":null}}]},"workspace":{"blocks":{"languageVersion":0,"blocks":[{"type":"dc_root_enchantment","id":"/~Lr;SG!hMj(,;J!]vap","x":20,"y":20,"deletable":false,"movable":false},{"type":"dc_reaction","id":"W*I[n}W/e|5WV/![k/f5","x":200,"y":20,"inline":false,"fields":{"EVENT":"monster_summoned"},"inputs":{"CONDITION":{"block":{"type":"dc_predicate_and","id":"lDbLq}w.mL]GzjYL+93C","inputs":{"LEFT":{"block":{"type":"dc_value_event","id":"}2#0As~2GKfob3t|+6]#","fields":{"FIELD":"is_played"}}},"RIGHT":{"block":{"type":"dc_predicate_compare","id":"5h;U7#Gq7`,dEe*v1LWu","fields":{"OPERATOR":"eq"},"inputs":{"LEFT":{"block":{"type":"dc_value_attribute","id":"H]PBdnOI.U6,n?1~l|mA","fields":{"ATTRIBUTE":"id"},"inputs":{"SELECTOR":{"block":{"type":"dc_selector_slot_of","id":"GVPJQU0Q-dg$4e59T}3/","inputs":{"SELECTOR":{"shadow":{"type":"dc_selector_self","id":"-r-S%A:ULdFl2B?,Jej4"},"block":{"type":"dc_selector_event_entity","id":"Gbo/bzA:0R#2uAt`(j_U","fields":{"ROLE":"monster"}}}}}}}}},"RIGHT":{"block":{"type":"dc_value_attribute","id":"fH?1tTM-:lf9$3ynsQj~","fields":{"ATTRIBUTE":"id"},"inputs":{"SELECTOR":{"block":{"type":"dc_selector_slot_of","id":"Kf=df]0b|qob0Ohh)KvW","inputs":{"SELECTOR":{"shadow":{"type":"dc_selector_self","id":"-r-S%A:ULdFl2B?,Jej4"},"block":{"type":"dc_selector_self","id":"=h*mh`gL;39bSU,,r`$:"}}}}}}}}}}}}}}},"next":{"block":{"type":"dc_effect_then","id":"EddkS)fA/C9BG8y1RoQ(","inline":false,"inputs":{"EFFECT":{"block":{"type":"dc_action_choose","id":"F=Lpk$^5^t!YD^+[@)A*","inline":false,"inputs":{"PLAYER":{"shadow":{"type":"dc_selector_you","id":"AIiDFgyxtA2/hLN2V.~)"},"block":{"type":"dc_selector_you","id":".?y+wMZB05,[i7RKqnuV"}},"OPTIONS":{"shadow":{"type":"dc_selector_deck","id":"Fe]dHf1ZccC{bE1DTo4X"},"block":{"type":"dc_selector_discover","id":"*gkP/g`MId(e[;sZnM8E","inline":false,"inputs":{"COUNT":{"block":{"type":"dc_value_number","id":"Z7]#{RVjsiFnG]#@3B?e","fields":{"VALUE":3}}},"PREDICATE":{"block":{"type":"dc_predicate_and","id":"~S)Sb`pVt5?TI%-=NQsb","inputs":{"LEFT":{"block":{"type":"dc_predicate_and","id":"|fMx~2jTtza8IZf()H#^","inline":false,"inputs":{"LEFT":{"block":{"type":"dc_predicate_card_type","id":"hs`l%JyIAN|]iE^u40|L","fields":{"TYPE":"monster"}}},"RIGHT":{"block":{"type":"dc_predicate_rarity","id":"BdZGU5Q=vR[i]Q4Ism5[","fields":{"OPERATOR":"lt","RARITY":"TOKEN"}}}}}},"RIGHT":{"block":{"type":"dc_predicate_attribute_compare","id":"^RA-*LHK]G?D]}:4njtP","fields":{"ATTRIBUTE":"cost","OPERATOR":"lt"},"inputs":{"VALUE":{"block":{"type":"dc_value_attribute","id":"fen,3)BOiIw]wt.^a}7+","fields":{"ATTRIBUTE":"cost"},"inputs":{"SELECTOR":{"block":{"type":"dc_selector_event_snapshot","id":"l{}Jt2BBJXVoGw.G;G0s","fields":{"ROLE":"monster"}}}}}}}}}}}},"CONTROLLER":{"block":{"type":"dc_selector_you","id":"hWmYkK4DJX%1H+L83iN."}}}}}}}},"THEN":{"block":{"type":"dc_action_transform_card","id":"_cwr+-lE6IdcLuaJU*je","inputs":{"TARGET":{"block":{"type":"dc_selector_event_entity","id":"C)7=f/tu:YnE`JJ@l)?l","fields":{"ROLE":"monster"}}},"NEW_CARD":{"block":{"type":"dc_selector_choice_selected","id":"2Ob0Zzg=-9.{Y1#*flm!"}}},"next":{"block":{"type":"dc_action_remove_enchantment","id":"?wa^3;6U-Jz~6u6nkzC{","inputs":{"TARGET":{"shadow":{"type":"dc_selector_all_enchantments","id":"AgNgEu/]~{r^6?##,TZp"},"block":{"type":"dc_selector_self","id":"IdO531PzKI%N}e%-/;,k"}}}}}}}}}}}]}},"workspaceValid":true,"import":{"adapter":"uc-editor","adapterVersion":1,"key":"enchantment:7"}},{"contentId":"ea0b012f-aeb8-4805-aa2a-47ffd39ed160","importKey":"card:5","kind":"monster","definition":{"name":"Example Monster 1","description":"{{KW:MAGIC}}: Deal {{DMG:3}} to monsters adjacent to this. {{KW:BULLSEYE}}: Gain {{KW:DODGE}} (1).","rarity":"COMMON","cost":9,"attack":6,"hp":9,"tribes":[],"keywords":[],"statuses":{},"image":{"source":"existing","name":"Knight_Knight"}},"implementation":{"irVersion":1,"variables":[],"targets":null,"need":null,"abilities":[{"nodeId":"[U??}g2wortLpP}W}#:Y","ability":"magic","effect":{"nodeId":"jUA|9Bu[P[4csGY_LKnq","node":"action.hit","damage":{"nodeId":"pjoI8N{{|PA#uoVYO6H,","node":"value.literal","value":3},"target":{"nodeId":"P%oq#OunTG7[wdK:nTRA","node":"selector.relative_board","selector":{"nodeId":"%|gylhfk]zI2lh8-kFi!","node":"selector.self"},"relation":"adjacent"}}},{"nodeId":"V.mhSQ,s-E3zwI_Q$V5*","ability":"bullseye","effect":{"nodeId":"B3IXgAzfU[)Q~T,~dG-$","node":"action.set_status","status_id":"DODGE","value":{"nodeId":"Eir3_:C;J1nf|eL}x#1d","node":"value.math","left":{"nodeId":"5R^_nX,|m8uuYW6`^l)+","node":"value.status","selector":{"nodeId":"K;D(D0PH=I=mWS,YQ:vN","node":"selector.self"},"status":"DODGE"},"right":{"nodeId":"JgU+FxUc7@[Fty_-VuMu","node":"value.literal","value":1},"operator":"add"},"target":{"nodeId":"(0kv@0$;{o8[6$;g.%-B","node":"selector.self"}}}],"reactions":[]},"workspace":{"blocks":{"languageVersion":0,"blocks":[{"type":"dc_root_monster","id":"dq?HZZeLQ|9jZ{(JBpMZ","x":20,"y":20,"deletable":false,"movable":false},{"type":"dc_ability","id":"[U??}g2wortLpP}W}#:Y","x":200,"y":20,"fields":{"ABILITY":"magic"},"next":{"block":{"type":"dc_action_hit","id":"jUA|9Bu[P[4csGY_LKnq","inputs":{"DAMAGE":{"shadow":{"type":"dc_value_number","id":"^RryZ=AVXl~YnZ:%hd_X","fields":{"VALUE":3}},"block":{"type":"dc_value_number","id":"pjoI8N{{|PA#uoVYO6H,","fields":{"VALUE":3}}},"TARGET":{"shadow":{"type":"dc_selector_target","id":"4xNKwn_R+oH#L97ignz+"},"block":{"type":"dc_selector_relative_board","id":"P%oq#OunTG7[wdK:nTRA","fields":{"RELATION":"adjacent"},"inputs":{"SELECTOR":{"shadow":{"type":"dc_selector_self","id":"Q@QH{cE`#yx{mTd3Fu=z"},"block":{"type":"dc_selector_self","id":"%|gylhfk]zI2lh8-kFi!"}}}}}}}}},{"type":"dc_ability","id":"V.mhSQ,s-E3zwI_Q$V5*","x":200,"y":220,"fields":{"ABILITY":"bullseye"},"next":{"block":{"type":"dc_action_set_status","id":"B3IXgAzfU[)Q~T,~dG-$","fields":{"STATUS":"DODGE"},"inputs":{"VALUE":{"block":{"type":"dc_value_math","id":"Eir3_:C;J1nf|eL}x#1d","inline":true,"fields":{"OPERATOR":"add"},"inputs":{"LEFT":{"block":{"type":"dc_value_status","id":"5R^_nX,|m8uuYW6`^l)+","fields":{"STATUS":"DODGE"},"inputs":{"SELECTOR":{"block":{"type":"dc_selector_self","id":"K;D(D0PH=I=mWS,YQ:vN"}}}}},"RIGHT":{"block":{"type":"dc_value_number","id":"JgU+FxUc7@[Fty_-VuMu","fields":{"VALUE":1}}}}}},"TARGET":{"block":{"type":"dc_selector_self","id":"(0kv@0$;{o8[6$;g.%-B"}}}}}}]}},"workspaceValid":true,"import":{"adapter":"uc-editor","adapterVersion":1,"key":"card:5"}},{"contentId":"594b09b0-23cf-4ab3-ab91-5a290fad3de6","importKey":"card:6","kind":"monster","definition":{"name":"Example Monster 2","description":"After an enemy monster with {{KW:HASTE}} is summoned, it attacks this monster. {{KW:MAGIC}}: Give all monsters in the enemy hand {{KW:HASTE}}.","rarity":"RARE","cost":5,"attack":5,"hp":6,"tribes":[],"keywords":[],"statuses":{},"image":{"source":"client","assetId":"601b6c00-745a-4e96-92f9-b27bfd271229"}},"implementation":{"irVersion":1,"variables":[],"targets":null,"need":null,"abilities":[{"nodeId":"3_uhWwv4O?zSXtCuR(U/","ability":"magic","effect":{"nodeId":"WVJY!]/.VY=?:~!2l@a~","node":"action.add_keyword","keyword":"HASTE","target":{"nodeId":"U$ap2Kx;+*S,G8@-Fqbx","node":"selector.zone","player":{"nodeId":".EpsH*Q7o3iPVk@b5(:z","node":"selector.opponent"},"zone":"HAND"}}}],"reactions":[{"nodeId":"dCI$u8jV@z#nViL?aar}","event":"monster_summoned","condition":{"nodeId":"`e[|S8`_o,a70.__;PWN","node":"predicate.and","predicates":[{"nodeId":"bidXA;|{a+Y,Er?DDf|0","node":"predicate.compare","left":{"nodeId":"/]_+]7X.6(wcu,Q4!LY)","node":"value.attribute","selector":{"nodeId":"iA${6IrA(Y^R)~_Db8#A","node":"selector.event_snapshot","role":"monster"},"attribute":"controller"},"right":{"nodeId":"Gqu*z+yvyznV(?l[/i~=","node":"value.attribute","selector":{"nodeId":"BT3Wv?SneDH`7j*yb?6E","node":"selector.self"},"attribute":"controller"},"operator":"ne"},{"nodeId":"`aXa8iGiuRPV(Z}NYWxM","node":"predicate.has_keyword","keyword":"HASTE"}]},"effect":{"nodeId":"4R(ahx_fCa0X#k2Cei/s","node":"action.attack","attacker":{"nodeId":"}.I4:+Y;PyOV38Xke;5@","node":"selector.event_entity","role":"monster"},"defender":{"nodeId":"eh_6xxj.m^^CWcwc|,IW","node":"selector.self"}}}]},"workspace":{"blocks":{"languageVersion":0,"blocks":[{"type":"dc_root_monster","id":"mviaTz6b{:OJYY)/q(0:","x":20,"y":20,"deletable":false,"movable":false},{"type":"dc_reaction","id":"dCI$u8jV@z#nViL?aar}","x":200,"y":20,"fields":{"EVENT":"monster_summoned"},"inputs":{"CONDITION":{"block":{"type":"dc_predicate_and","id":"`e[|S8`_o,a70.__;PWN","inputs":{"LEFT":{"block":{"type":"dc_predicate_compare","id":"bidXA;|{a+Y,Er?DDf|0","fields":{"OPERATOR":"ne"},"inputs":{"LEFT":{"block":{"type":"dc_value_attribute","id":"/]_+]7X.6(wcu,Q4!LY)","fields":{"ATTRIBUTE":"controller"},"inputs":{"SELECTOR":{"block":{"type":"dc_selector_event_snapshot","id":"iA${6IrA(Y^R)~_Db8#A","fields":{"ROLE":"monster"}}}}}},"RIGHT":{"block":{"type":"dc_value_attribute","id":"Gqu*z+yvyznV(?l[/i~=","fields":{"ATTRIBUTE":"controller"},"inputs":{"SELECTOR":{"block":{"type":"dc_selector_self","id":"BT3Wv?SneDH`7j*yb?6E"}}}}}}}},"RIGHT":{"block":{"type":"dc_predicate_has_keyword","id":"`aXa8iGiuRPV(Z}NYWxM","fields":{"KEYWORD":"HASTE"}}}}}}},"next":{"block":{"type":"dc_action_attack","id":"4R(ahx_fCa0X#k2Cei/s","inputs":{"ATTACKER":{"shadow":{"type":"dc_selector_self","id":"sMLax0j6SKWjVMf@(F;$"},"block":{"type":"dc_selector_event_entity","id":"}.I4:+Y;PyOV38Xke;5@","fields":{"ROLE":"monster"}}},"DEFENDER":{"shadow":{"type":"dc_selector_target","id":"w,Jh!KueAhPr(fmCF)dS"},"block":{"type":"dc_selector_self","id":"eh_6xxj.m^^CWcwc|,IW"}}}}}},{"type":"dc_ability","id":"3_uhWwv4O?zSXtCuR(U/","x":200,"y":220,"fields":{"ABILITY":"magic"},"next":{"block":{"type":"dc_action_add_keyword","id":"WVJY!]/.VY=?:~!2l@a~","fields":{"KEYWORD":"HASTE"},"inputs":{"TARGET":{"shadow":{"type":"dc_selector_target","id":",)#J$p}_{}nw8a8NanzL"},"block":{"type":"dc_selector_zone","id":"U$ap2Kx;+*S,G8@-Fqbx","fields":{"ZONE":"HAND"},"inputs":{"PLAYER":{"shadow":{"type":"dc_selector_you","id":"Obk{[K_p@7_-xyx1EQi["},"block":{"type":"dc_selector_opponent","id":".EpsH*Q7o3iPVk@b5(:z"}}}}}}}}}]}},"workspaceValid":true,"import":{"adapter":"uc-editor","adapterVersion":1,"key":"card:6"}},{"contentId":"edc85f7c-b060-4694-9371-2c5b1869aeb0","importKey":"card:8","kind":"spell","definition":{"name":"Example Spell","description":"Equip the Example Artifact.","rarity":"EPIC","cost":3,"keywords":[],"statuses":{},"soulId":"INTEGRITY","image":{"source":"existing","name":"Gacha_Ball"}},"implementation":{"irVersion":1,"variables":[],"targets":null,"need":null,"abilities":[{"nodeId":"wVx2@U:b2zMVZ%=jym0Q","ability":"magic","effect":{"nodeId":"yD6Falj/.N)Gg[9b@ul6","node":"action.add_artifact","player":{"nodeId":"-HGVwg6;hxPluwXU}0}P","node":"selector.you"},"artifact":{"nodeId":"yD6Falj/.N)Gg[9b@ul6","node":"selector.artifact_by_name","name":"Example Artifact"}}}],"reactions":[]},"workspace":{"blocks":{"languageVersion":0,"blocks":[{"type":"dc_root_spell","id":"#./ymAS(7j|Mo+=!@okx","x":20,"y":20,"deletable":false,"movable":false},{"type":"dc_ability","id":"wVx2@U:b2zMVZ%=jym0Q","x":200,"y":20,"fields":{"ABILITY":"magic"},"next":{"block":{"type":"dc_action_add_artifact","id":"yD6Falj/.N)Gg[9b@ul6","fields":{"NAME":"Example Artifact"},"inputs":{"PLAYER":{"shadow":{"type":"dc_selector_you","id":"-HGVwg6;hxPluwXU}0}P"}}}}}}]}},"workspaceValid":true}],"assets":[{"assetId":"601b6c00-745a-4e96-92f9-b27bfd271229","mimeType":"image/png","data":"iVBORw0KGgoAAAANSUhEUgAAAKAAAABaCAYAAAA/xl1SAAABhWlDQ1BJQ0MgcHJvZmlsZQAAKJF9kb1Lw0AYxp+mlhapONhBxCFDdbKLiohTqWIRLJS2QqsOJpd+QZOGJMXFUXAtOPixWHVwcdbVwVUQBD9A/APESdFFSnwvKbSI8Y7jfjz3Pg937wFCq8ZUsy8OqJplZJIJMV9YFYOvCCFIcw4BiZl6KruYg+f4uoeP73cxnuVd9+cYUIomA3wicZzphkW8QTyzaemc94kjrCIpxOfEEwZdkPiR67LLb5zLDgs8M2LkMvPEEWKx3MNyD7OKoRJPE0cVVaN8Ie+ywnmLs1prsM49+QvDRW0ly3Vao0hiCSmkIUJGA1XUYCFGu0aKiQydJzz8I44/TS6ZXFUwciygDhWS4wf/g9+9NUtTk25SOAEEXmz7YwwI7gLtpm1/H9t2+wTwPwNXWtdfbwGzn6Q3u1r0CBjcBi6uu5q8B1zuAMNPumRIjuSnJZRKwPsZfVMBGLoF+tfcvnXOcfoA5KhXyzfAwSEwXqbsdY93h3r79m9Np38/l0VytRAU+y0AAAAJcEhZcwAACxMAAAsTAQCanBgAAAInSURBVHja7d1BTsMwEEZhF/W83IAVN+DCYcEOAUnpeDy2vyexCKAMNJ6nf+IGbq21owGDePESwAKEBQhYgLAAd+Pt+PrYtb4FiK2572y+1lp7v/18vHp9BgQyDHjW6Y8en50/+ud59Hyr1e9tZgbEUG4taSuut/me/X71x2RSBsTaBozupNGdu1t9GRAMmNFJ0dOy49y7CwwIBuxhvtEZZbX61UzIgJABK5hkN2RAoGIGxF4mZEDIgJjPjAwIBpQBZUAGBAPOlAGP128vwMffn8+qE11fBgQucB/dSTJgTdN5JgQy4IoZEDIgkGfAKhnw6pQZNY1WO0/V68OAWHsKHv3cKWpfHwaEDMiEdaddGRAM2KPTqk2/0dNn1t7y7NeHAbH2FDx6rxG1rw8DQgZEPRPKgGDAnhnj6tejp8asdyrPMgW7DwhTcE/sBdfGXjBkwBUzIGRAYLwBf+uk7Ok3+7yzvCM6+/owIPaagu0Fz5kB7QVDBsyctjDXdMyAYMCITorqtKxp8dnni6v9dSz3AWEK7snZNCUTjsX/CYEMuHLGgAwIjDMg061pRgYEA8qAMiADggGZkPkYEAwY0WlMmGs+GRAMWDFzOM49lgHBgCPMF51henfubvVlQDDgiM6Nnp7Vj63PgGDADPNFT2vRnb96fRkQDFiJKCP+t9NXqV8FBgQD9siWUUZdvT4DggFn/gVGd/7u9RkQDAgwICxAwAKEBQhc5RPcVpnBZPJaFgAAAABJRU5ErkJggg=="},{"assetId":"988b808a-5a9a-4484-8177-c15ad602f436","mimeType":"image/png","data":"iVBORw0KGgoAAAANSUhEUgAAANwAAAD6CAMAAAD9cdmYAAAAAXNSR0IB2cksfwAAAARnQU1BAACxjwv8YQUAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAAAxQTFRFAAAAAAAAALP/AAAAvItDowAAAAF0Uk5TAEDm2GYAAAABYktHRACIBR1IAAAACXBIWXMAAAsTAAALEwEAmpwYAAABIklEQVR42u3dQQrDIBBA0bT3P3RXhVJKkoozjM77F9C30YgBj0OSJEmSJEmSJEmSJEmSJEmSJEmSpM+eiwUHtwPusUhwcHBwcHBwcHC1cRWAd8YfgsHBwf2c9Ds4OLg82BUQDg5uPuwMCAcHlweDg9sNlwkcgcHBwS0Eg4NrihuFwcHB5cLg4OByYXBwu+IigDNgcHBwuTA4uI64kQWgFAwObiHcyMFyFgwObnfcN3DkwmImDA6uG+4fYAQMDq4j7g4wCgYH1xV3BoyEwcF1xl1BysPg4IriZgBnXqbAwXXHZWzccHBw9z+k4eDg4n62iYTBwcHlBwfXBVcBGAaDg4ODg4M7ajyMAgfXCSdJkiRJkiRJkiRJkiRJkiRJkiRJ2qcXWMheMaARPREAAAAASUVORK5CYII="}]};

  const CARD_RARITIES = new Set([
    'BASE',
    'COMMON',
    'RARE',
    'EPIC',
    'LEGENDARY',
    'DETERMINATION',
    'TOKEN',
  ]);

  const ARTIFACT_RARITIES = new Set([
    'BASE',
    'COMMON',
    'LEGENDARY',
    'TOKEN',
  ]);

  const STANDARD_SOULS = [
    'KINDNESS',
    'DETERMINATION',
    'PATIENCE',
    'BRAVERY',
    'INTEGRITY',
    'PERSEVERANCE',
    'JUSTICE',
  ];

  const KEYWORDS = [
    'CHARGE',
    'HASTE',
    'TAUNT',
    'KR',
    'CANDY',
    'ARMOR',
    'TRANSPARENCY',
    'DISARMED',
    'INVULNERABLE',
    'SILENCED',
    'WANTED',
    'DARKSPAWN',
    'FLOWERY_POWER',
  ];

  const STATUSES = [
    'PARALYZED',
    'DODGE',
    'LOOP',
  ];

  const TRIBES = new Set([
    'ALL',
    'TEMMIE',
    'DOG',
    'AMALGAMATE',
    'G_FOLLOWER',
    'LOST_SOUL',
    'FROGGIT',
    'MOLD',
    'SNAIL',
    'BOMB',
    'PLANT',
    'ROYAL_GUARD',
    'CHAOS_WEAPON',
    'PIECE',
    'ARACHNID',
    'ROYAL_INVENTION',
    'PLUG',
    'THRASHING_PART',
    'BARGAIN',
    'DANCE',
    'GIGA_ATTACK',
    'ROUND',
    'PACK',
  ]);

  const ALL_ABILITIES = [
    'game_start',
    'magic',
    'synergy',
    'dust',
    'delay',
    'turn_start',
    'turn_end',
    'shock',
    'support',
    'turbo',
    'bullseye',
    'program',
  ];

  const EVENT_OPTIONS = [
    ['card drawn', 'card_drawn'],
    ['card overdrawn', 'card_overdrawn'],
    ['card revealed', 'card_revealed'],
    ['entity damaged', 'entity_damaged'],
    ['entity healed', 'entity_healed'],
    ['Dodge consumed', 'dodge_consumed'],
    ['attack declared', 'attack_declared'],
    ['attack resolved', 'attack_resolved'],
    ['card played', 'card_played'],
    ['monster summoned', 'monster_summoned'],
    ['spell cast', 'spell_cast'],
    ['monster killed', 'monster_killed'],
    ['gold spent', 'gold_spent'],
    ['ability triggered', 'ability_triggered'],
    ['board slot enchanted', 'board_slot_enchanted'],
    ['enchantment removed', 'enchantment_removed'],
  ];

  const EVENT_DETAILS = {
    card_drawn: {
      live: ['subject', 'card', 'player'],
      snapshots: ['subject', 'card'],
      values: [],
    },
    card_overdrawn: {
      live: ['subject', 'card', 'player'],
      snapshots: ['subject', 'card'],
      values: [],
    },
    card_revealed: {
      live: ['subject', 'card'],
      snapshots: ['subject', 'card'],
      values: [],
    },
    entity_damaged: {
      live: ['subject', 'target'],
      snapshots: ['subject', 'target'],
      values: ['amount', 'killed', 'excess_damage', 'kind'],
    },
    entity_healed: {
      live: ['subject', 'target'],
      snapshots: ['subject', 'target'],
      values: ['amount'],
    },
    dodge_consumed: {
      live: ['subject', 'monster'],
      snapshots: ['subject', 'monster'],
      values: [],
    },
    attack_declared: {
      live: ['subject', 'attacker', 'defender'],
      snapshots: ['subject', 'attacker', 'defender'],
      values: [],
    },
    attack_resolved: {
      live: ['subject', 'attacker', 'defender'],
      snapshots: ['subject', 'attacker', 'defender'],
      values: [
        'damage_to_attacker',
        'damage_to_defender',
        'attacker_dead',
        'defender_dead',
      ],
    },
    card_played: {
      live: ['subject', 'card', 'player'],
      snapshots: ['subject', 'card'],
      values: ['has_need_condition', 'need_fulfilled'],
    },
    monster_summoned: {
      live: ['subject', 'monster', 'player', 'target'],
      snapshots: ['subject', 'monster', 'target'],
      values: ['is_played'],
    },
    spell_cast: {
      live: ['subject', 'card', 'player', 'target'],
      snapshots: ['subject', 'card', 'target'],
      values: ['is_played'],
    },
    monster_killed: {
      live: ['subject', 'monster', 'killer'],
      snapshots: ['subject', 'monster', 'killer'],
      values: ['cause'],
    },
    gold_spent: {
      live: ['player', 'card'],
      snapshots: ['subject', 'card'],
      values: ['amount', 'reason', 'is_generated'],
    },
    ability_triggered: {
      live: ['subject', 'entity'],
      snapshots: ['subject', 'entity'],
      values: ['ability'],
    },
    board_slot_enchanted: {
      live: [
        'player',
        'slot',
        'enchantment',
        'replaced_enchantment',
      ],
      snapshots: [
        'subject',
        'slot',
        'enchantment',
        'replaced_enchantment',
      ],
      values: [],
    },
    enchantment_removed: {
      live: ['player', 'slot', 'enchantment'],
      snapshots: ['subject', 'slot', 'enchantment'],
      values: ['reason'],
    },
  };

  const ROOT_CONFIG = {
    monster: {
      block: 'dc_root_monster',
      targets: true,
      need: true,
      abilities: [
        'magic',
        'synergy',
        'dust',
        'delay',
        'turn_start',
        'turn_end',
        'shock',
        'support',
        'turbo',
        'bullseye',
        'program',
      ],
    },
    spell: {
      block: 'dc_root_spell',
      targets: true,
      need: false,
      abilities: ['magic', 'turbo'],
    },
    artifact: {
      block: 'dc_root_artifact',
      targets: false,
      need: false,
      abilities: [
        'game_start',
        'turn_start',
        'turn_end',
      ],
    },
    enchantment: {
      block: 'dc_root_enchantment',
      targets: false,
      need: false,
      abilities: [
        'turn_start',
        'turn_end',
      ],
    },
  };

  const ABILITY_LABELS = {
    game_start: 'Game start',
    magic: 'Magic',
    synergy: 'Synergy',
    dust: 'Dust',
    delay: 'Delay',
    turn_start: 'Turn start',
    turn_end: 'Turn end',
    shock: 'Shock',
    support: 'Support',
    turbo: 'Turbo',
    bullseye: 'Bullseye',
    program: 'Program',
  };

  const ABILITY_OPTIONS = ALL_ABILITIES.map((ability) => [
    ABILITY_LABELS[ability] || ability,
    ability,
  ]);

  const COMPARISON_OPTIONS = [
    ['=', 'eq'],
    ['≠', 'ne'],
    ['<', 'lt'],
    ['≤', 'le'],
    ['>', 'gt'],
    ['≥', 'ge'],
  ];

  const ENABLED_OPTIONS = [
    ['Enable', 'true'],
    ['Disable', 'false'],
  ];

  const ENUM_VALUES = {
    ability: ALL_ABILITIES.map(
      (value) => [ABILITY_LABELS[value] || value, value.toUpperCase()]
    ),
    artifactRarity: [...ARTIFACT_RARITIES].map(
      (value) => [value, value]
    ),
    cardKeyword: KEYWORDS.map((value) => [value, value]),
    cardRarity: [...CARD_RARITIES].map(
      (value) => [value, value]
    ),
    cardStatus: STATUSES.map((value) => [value, value]),
    cardZone: [
      ['Board', 'BOARD'],
      ['Hand', 'HAND'],
      ['Deck', 'DECK'],
      ['Dustpile', 'DUSTPILE'],
      ['Erased', 'ERASED'],
    ],
    damageKind: [
      ['Combat', 'COMBAT'],
      ['Spell', 'SPELL'],
      ['Ability', 'ABILITY'],
      ['Fatigue', 'FATIGUE'],
    ],
    expansion: [
      ['BASE', 'BASE'],
      ['DELTARUNE', 'DELTARUNE'],
      ['UTY', 'UTY'],
    ],
    killCause: [
      ['Combat', 'COMBAT'],
      ['Damage effect', 'DAMAGE_EFFECT'],
      ['Destroy effect', 'DESTROY_EFFECT'],
      ['Other', 'OTHER'],
    ],
    tribe: [...TRIBES].map((value) => [value, value]),
    goldSpendReason: [
      ['play monster', 'play_monster'],
      ['play spell', 'play_spell'],
      ['Program', 'program'],
      ['effect', 'effect'],
    ],
    enchantmentRemovalReason: [
      ['expired', 'expired'],
      ['removed', 'removed'],
      ['replaced', 'replaced'],
      ['transformed', 'transformed'],
    ],
    soul: STANDARD_SOULS.map((value) => [value, value]),
  };

  const ATTRIBUTE_OPTIONS = [
    ['ID', 'id'],
    ['template ID', 'templateId'],
    ['name', 'name'],
    ['rarity', 'rarity'],
    ['cost', 'cost'],
    ['ATK', 'attack'],
    ['HP', 'hp'],
    ['maximum HP', 'maxHp'],
    ['missing HP', 'missingHp'],
    ['age', 'age'],
    ['position', 'position'],
    ['controller', 'controller'],
    ['creator', 'creator'],
    ['gold', 'gold'],
    ['turn', 'turn'],
    ['counter', 'counter'],
    ['quest goal', 'questGoal'],
  ];

  const SELECTOR_ATTRIBUTE_OPTIONS = ATTRIBUTE_OPTIONS.map(
    ([label, value]) => [`${label} of`, value]
  );

  const INTEGER_ATTRIBUTES = new Set([
    'id',
    'templateId',
    'cost',
    'attack',
    'hp',
    'maxHp',
    'missingHp',
    'age',
    'position',
    'controller',
    'creator',
    'gold',
    'turn',
    'counter',
    'questGoal',
  ]);

  const ENUM_ATTRIBUTES = new Set([
    'rarity',
  ]);

  const INTEGER_EVENT_FIELDS = new Set([
    'amount',
    'excess_damage',
    'damage_to_attacker',
    'damage_to_defender',
  ]);

  const BOOLEAN_EVENT_FIELDS = new Set([
    'killed',
    'attacker_dead',
    'defender_dead',
    'is_played',
    'has_need_condition',
    'need_fulfilled',
    'is_generated',
  ]);

  const ENUM_EVENT_FIELDS = new Set([
    'ability',
    'cause',
    'kind',
    'reason',
  ]);

  const SIMPLE_EXPRESSIONS = {
    dc_selector_self: {
      label: 'this',
      node: 'selector.self',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_target: {
      label: 'target',
      node: 'selector.target',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_you: {
      label: 'you',
      node: 'selector.you',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_opponent: {
      label: 'opponent',
      node: 'selector.opponent',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_turn_player: {
      label: 'turn player',
      node: 'selector.turn_player',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_all_players: {
      label: 'all players',
      node: 'selector.all_players',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_ally_monsters: {
      label: 'ally monsters',
      node: 'selector.ally_monsters',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_enemy_monsters: {
      label: 'enemy monsters',
      node: 'selector.enemy_monsters',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_all_monsters: {
      label: 'all monsters',
      node: 'selector.all_monsters',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_allies: {
      label: 'all allies',
      node: 'selector.allies',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_enemies: {
      label: 'all enemies',
      node: 'selector.enemies',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_hand: {
      label: 'your hand',
      node: 'selector.hand',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_deck: {
      label: 'your deck',
      node: 'selector.deck',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_ally_slots: {
      label: 'ally board slots',
      node: 'selector.ally_slots',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_enemy_slots: {
      label: 'enemy board slots',
      node: 'selector.enemy_slots',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_all_slots: {
      label: 'all board slots',
      node: 'selector.all_slots',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_this_slot_monster: {
      label: 'monster in this enchantment\'s slot',
      node: 'selector.this_slot_monster',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_all_enchantments: {
      label: 'all enchantments',
      node: 'selector.all_enchantments',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_card_library: {
      label: 'all cards',
      node: 'selector.card_library',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_next_lost_soul: {
      label: 'next Lost SOUL',
      node: 'selector.next_lost_soul',
      output: 'Selector',
      colour: 180,
    },
    dc_selector_choice_selected: {
      label: 'chosen option',
      node: 'selector.choice_selected',
      output: 'Selector',
      colour: 330,
    },
    dc_selector_choice_not_selected: {
      label: 'options not chosen',
      node: 'selector.choice_not_selected',
      output: 'Selector',
      colour: 330,
    },
    dc_selector_killer: {
      label: 'killer',
      node: 'selector.killer',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_attacker: {
      label: 'attacker',
      node: 'selector.attacker',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_defender: {
      label: 'defender',
      node: 'selector.defender',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_loop_copy: {
      label: 'Loop copy',
      node: 'selector.loop_copy',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_trigger_card: {
      label: 'spell that triggered Shock',
      node: 'selector.trigger_card',
      output: 'Selector',
      colour: 210,
    },
    dc_selector_death_slot: {
      label: 'slot where this monster died',
      node: 'selector.death_slot',
      output: 'Selector',
      colour: 210,
    },
    dc_predicate_damaged: {
      label: 'is damaged',
      node: 'predicate.damaged',
      output: ['CandidatePredicate', 'Condition'],
      colour: 120,
    },
    dc_predicate_dead: {
      label: 'is dead',
      node: 'predicate.dead',
      output: ['CandidatePredicate', 'Condition'],
      colour: 120,
    },
    dc_predicate_has_negative_effects: {
      label: 'has negative effects',
      node: 'predicate.has_negative_effects',
      output: ['CandidatePredicate', 'Condition'],
      colour: 120,
    },
    dc_predicate_has_any_tribe: {
      label: 'has any Tribe',
      node: 'predicate.has_any_tribe',
      output: ['CandidatePredicate', 'Condition'],
      colour: 120,
    },
    dc_value_synergy_triggered: {
      label: 'Synergy was triggered',
      node: 'value.synergy_triggered',
      output: ['Value', 'Condition'],
      colour: 65,
    },
  };

  const EXPRESSION_SPECS = {
    dc_selector_zone: {
      node: 'selector.zone',
      inputs: {
        player: 'PLAYER',
      },
      fields: {
        zone: 'ZONE',
      },
    },
    dc_selector_controller_of: {
      node: 'selector.controller_of',
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_selector_opponent_of: {
      node: 'selector.opponent_of',
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_selector_named: {
      node: (block) => (
        `selector.${block.getFieldValue('KIND')}_by_name`
      ),
      fields: {
        name: ['NAME', (value) => value.trim()],
      },
    },
    dc_selector_artifact_of_player: {
      node: 'selector.artifact_of_player',
      inputs: {
        player: 'PLAYER',
      },
      fields: {
        name: ['NAME', (value) => value.trim()],
      },
    },
    dc_selector_board_slots_of: {
      node: 'selector.board_slots_of',
      inputs: {
        player: 'PLAYER',
      },
    },
    dc_selector_enchantments_of: {
      node: 'selector.enchantments_of',
      inputs: {
        player: 'PLAYER',
      },
    },
    dc_selector_relative_board: {
      node: 'selector.relative_board',
      inputs: {
        selector: 'SELECTOR',
      },
      fields: {
        relation: 'RELATION',
      },
    },
    dc_selector_relative_hand: {
      node: 'selector.relative_hand',
      inputs: {
        selector: 'SELECTOR',
      },
      fields: {
        relation: 'RELATION',
      },
    },
    dc_selector_slot_of: {
      node: 'selector.slot_of',
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_selector_slot_content: {
      node: (block) => (
        block.getFieldValue('KIND') === 'monster'
          ? 'selector.monster_in_slot'
          : 'selector.enchantment_in_slot'
      ),
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_selector_combine: {
      node: (block) => (
        `selector.${block.getFieldValue('OPERATION')}`
      ),
      inputs: {
        left: 'LEFT',
        right: 'RIGHT',
      },
    },
    dc_selector_index: {
      node: 'selector.index',
      inputs: {
        index: 'INDEX',
        selector: 'SELECTOR',
      },
    },
    dc_selector_take: {
      node: 'selector.take',
      inputs: {
        count: 'COUNT',
        selector: 'SELECTOR',
      },
      fields: {
        side: 'SIDE',
      },
    },
    dc_selector_left_rightmost: {
      node: (block) => (
        block.getFieldValue('SIDE') === 'left'
          ? 'selector.leftmost'
          : 'selector.rightmost'
      ),
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_selector_limit_per: {
      node: 'selector.limit_per',
      inputs: {
        selector: 'SELECTOR',
        key: 'KEY',
        count: 'COUNT',
      },
    },
    dc_selector_copy: {
      node: (block) => (
        `selector.${block.getFieldValue('MODE')}`
      ),
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_selector_event_entity: {
      node: 'selector.event_entity',
      fields: {
        role: 'ROLE',
      },
    },
    dc_selector_event_snapshot: {
      node: 'selector.event_snapshot',
      fields: {
        role: 'ROLE',
      },
    },
    dc_selector_random: {
      node: 'selector.random',
      inputs: {
        selector: 'SELECTOR',
        count: 'COUNT',
      },
    },
    dc_selector_minmax: {
      node: (block) => (
        block.getFieldValue('MODE') === 'min'
          ? 'selector.min'
          : 'selector.max'
      ),
      inputs: {
        selector: 'SELECTOR',
        key: 'KEY',
        count: 'COUNT',
      },
    },
    dc_selector_sort: {
      node: 'selector.sort_by',
      inputs: {
        selector: 'SELECTOR',
        key: 'KEY',
      },
      fields: {
        reverse: [
          'DIRECTION',
          (value) => value === 'descending',
        ],
      },
    },
    dc_selector_distinct: {
      node: 'selector.distinct',
      inputs: {
        selector: 'SELECTOR',
        key: 'KEY',
      },
    },
    dc_selector_generate: {
      node: 'selector.generate',
      inputs: {
        selector: 'SELECTOR',
        count: 'COUNT',
        controller: 'CONTROLLER',
      },
    },
    dc_selector_discover: {
      node: 'selector.discover',
      inputs: {
        count: 'COUNT',
        controller: 'CONTROLLER',
      },
      nullableInputs: {
        predicate: 'PREDICATE',
      },
    },
    dc_selector_filter: {
      node: 'selector.filter',
      inputs: {
        selector: 'SELECTOR',
        predicate: 'PREDICATE',
      },
    },
    dc_predicate_card_type: {
      node: (block) => (
        block.getFieldValue('TYPE') === 'monster'
          ? 'predicate.is_monster'
          : 'predicate.is_spell'
      ),
    },
    dc_predicate_has_ability: {
      node: 'predicate.has_ability',
      fields: {
        ability: [
          'ABILITY',
          (value) => value.toUpperCase(),
        ],
      },
    },
    dc_predicate_has_keyword: {
      node: 'predicate.has_keyword',
      fields: {
        keyword: 'KEYWORD',
      },
    },
    dc_predicate_has_status: {
      node: 'predicate.has_status',
      fields: {
        status: 'STATUS',
      },
    },
    dc_predicate_has_tribe: {
      node: 'predicate.has_tribe',
      fields: {
        tribe: 'TRIBE',
      },
    },
    dc_predicate_expansion: {
      node: 'predicate.expansion',
      fields: {
        expansion: 'EXPANSION',
      },
    },
    dc_predicate_rarity: {
      node: 'predicate.rarity',
      fields: {
        operator: 'OPERATOR',
        rarity: 'RARITY',
      },
    },
    dc_predicate_generated: {
      node: 'predicate.generated',
      fields: {
        generated: [
          'GENERATED',
          (value) => value === 'true',
        ],
      },
    },
    dc_predicate_generated_by: {
      node: 'predicate.generated_by',
      inputs: {
        creator: 'CREATOR',
      },
    },
    dc_predicate_slot_state: {
      node: 'predicate.slot_state',
      fields: {
        state: 'STATE',
      },
    },
    dc_predicate_slot_has_enchantment: {
      node: 'predicate.slot_has_enchantment',
      fields: {
        name: ['NAME', (value) => value.trim()],
      },
    },
    dc_predicate_attribute_compare: {
      node: 'predicate.attribute_compare',
      inputs: {
        value: 'VALUE',
      },
      fields: {
        attribute: 'ATTRIBUTE',
        operator: 'OPERATOR',
      },
    },
    dc_predicate_compare: {
      node: 'predicate.compare',
      inputs: {
        left: 'LEFT',
        right: 'RIGHT',
      },
      fields: {
        operator: 'OPERATOR',
      },
    },
    dc_predicate_and: {
      node: 'predicate.and',
      inputLists: {
        predicates: ['LEFT', 'RIGHT'],
      },
    },
    dc_predicate_or: {
      node: 'predicate.or',
      inputLists: {
        predicates: ['LEFT', 'RIGHT'],
      },
    },
    dc_predicate_not: {
      node: 'predicate.not',
      inputs: {
        predicate: 'PREDICATE',
      },
    },
    dc_value_number: {
      node: 'value.literal',
      fields: {
        value: ['VALUE', Number],
      },
    },
    dc_value_boolean: {
      node: 'value.literal',
      fields: {
        value: [
          'VALUE',
          (value) => value === 'true',
        ],
      },
    },
    dc_value_enum: {
      node: 'value.enum',
      fields: {
        enum: 'ENUM',
        member: 'MEMBER',
      },
    },
    dc_value_event: {
      node: 'value.event',
      fields: {
        field: 'FIELD',
      },
    },
    dc_value_candidate_attribute: {
      node: 'value.candidate_attribute',
      fields: {
        attribute: 'ATTRIBUTE',
      },
    },
    dc_value_aggregate: {
      node: (block) => (
        `value.${block.getFieldValue('MODE')}`
      ),
      inputs: {
        selector: 'SELECTOR',
        value: 'VALUE',
      },
    },
    dc_value_count: {
      node: 'value.count',
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_value_exists: {
      node: 'value.exists',
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_value_attribute: {
      node: 'value.attribute',
      inputs: {
        selector: 'SELECTOR',
      },
      fields: {
        attribute: 'ATTRIBUTE',
      },
    },
    dc_value_base_stat: {
      node: 'value.base_stat',
      inputs: {
        selector: 'SELECTOR',
      },
      fields: {
        attribute: 'ATTRIBUTE',
      },
    },
    dc_value_buff: {
      node: 'value.buff',
      inputs: {
        selector: 'SELECTOR',
      },
      fields: {
        attribute: 'ATTRIBUTE',
      },
    },
    dc_value_status: {
      node: 'value.status',
      inputs: {
        selector: 'SELECTOR',
      },
      fields: {
        status: 'STATUS',
      },
    },
    dc_value_empty_slots: {
      node: 'value.empty_slots',
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_value_player_soul: {
      node: 'value.player_soul',
      inputs: {
        player: 'PLAYER',
      },
    },
    dc_value_unique_values: {
      node: 'value.unique_values',
      inputs: {
        selector: 'SELECTOR',
        value: 'VALUE',
      },
    },
    dc_value_unique_tribes: {
      node: 'value.unique_tribes',
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_value_count_unique_tribes: {
      node: 'value.count_unique_tribes',
      inputs: {
        selector: 'SELECTOR',
      },
    },
    dc_value_math: {
      node: 'value.math',
      inputs: {
        left: 'LEFT',
        right: 'RIGHT',
      },
      fields: {
        operator: 'OPERATOR',
      },
    },
    dc_value_negate: {
      node: 'value.negate',
      inputs: {
        value: 'VALUE',
      },
    },
    dc_value_clamp: {
      node: 'value.clamp',
      inputs: {
        value: 'VALUE',
        lower: 'LOWER',
        upper: 'UPPER',
      },
    },
    dc_value_least_greatest: {
      node: (block) => (
        block.getFieldValue('MODE') === 'least'
          ? 'value.least'
          : 'value.greatest'
      ),
      inputs: {
        left: 'LEFT',
        right: 'RIGHT',
      },
    },
  };

  function actionInput(
    name,
    check,
    argument,
    optional = false,
    transform = null
  ) {
    return {
      type: 'input',
      name,
      check,
      argument,
      optional,
      transform,
    };
  }

  function actionDropdown(name, options, argument) {
    return {
      type: 'dropdown',
      name,
      options,
      argument,
    };
  }

  function actionBoolean(name, options, argument) {
    return {
      type: 'boolean',
      name,
      options,
      argument,
    };
  }

  function actionDefinition(name, kind, argument) {
    return {
      type: 'definition',
      name,
      kind,
      argument,
    };
  }

  function actionVariable(name, argument) {
    return {
      type: 'variable',
      name,
      argument,
    };
  }

  function actionSpec(
    node,
    message,
    args,
    {
      fixed = {},
      customBlock = false,
    } = {}
  ) {
    return {
      node,
      message,
      args,
      fixed,
      customBlock,
    };
  }

  const ACTION_SPECS = {
    dc_action_reveal: actionSpec(
      'action.reveal',
      'Reveal %1',
      [
        actionInput('CARD', 'Selector', 'card'),
      ]
    ),
    dc_action_hit: actionSpec(
      'action.hit',
      'Deal %1 DMG to %2',
      [
        actionInput('DAMAGE', 'IntegerValue', 'damage'),
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_heal: actionSpec(
      'action.heal',
      'Heal %1 HP to %2',
      [
        actionInput('AMOUNT', 'IntegerValue', 'amount'),
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_kill: actionSpec(
      'action.kill',
      'Kill %1',
      [
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_attack: actionSpec(
      'action.attack',
      'Make %1 attack %2',
      [
        actionInput('ATTACKER', 'Selector', 'attacker'),
        actionInput('DEFENDER', 'Selector', 'defender'),
      ]
    ),
    dc_action_refresh_attacks: actionSpec(
      'action.refresh_attacks',
      'Let %1 be able to attack again',
      [
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_buff: actionSpec(
      'action.buff',
      'Give %1 cost %2 / ATK %3 / HP %4',
      [
        actionInput('TARGET', 'Selector', 'target'),
        actionInput('COST', 'IntegerValue', 'cost'),
        actionInput('ATTACK', 'IntegerValue', 'attack'),
        actionInput('HP', 'IntegerValue', 'hp'),
      ]
    ),
    dc_action_set_stats: actionSpec(
      'action.set_stats',
      'Set stats of %1: cost %2 ATK %3 HP %4',
      [
        actionInput('TARGET', 'Selector', 'target'),
        actionInput('COST', 'IntegerValue', 'cost', true),
        actionInput('ATTACK', 'IntegerValue', 'attack', true),
        actionInput('HP', 'IntegerValue', 'hp', true),
      ]
    ),
    dc_action_set_base_stats: actionSpec(
      'action.set_base_stats',
      'Set base stats of %1: cost %2 ATK %3 HP %4',
      [
        actionInput('TARGET', 'Selector', 'target'),
        actionInput('COST', 'IntegerValue', 'cost', true),
        actionInput('ATTACK', 'IntegerValue', 'attack', true),
        actionInput('HP', 'IntegerValue', 'hp', true),
      ]
    ),
    dc_action_swap_stats: actionSpec(
      'action.swap_stats',
      'Swap ATK and HP of %1',
      [
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_halve_stats: actionSpec(
      'action.halve_stats',
      'Halve stats of %1, %2, %3 cost',
      [
        actionInput('TARGET', 'Selector', 'target'),
        actionBoolean(
          'ROUND_UP',
          [
            ['round up', 'true'],
            ['round down', 'false'],
          ],
          'round_up'
        ),
        actionBoolean(
          'HALVE_COST',
          [
            ['include', 'true'],
            ['do not include', 'false'],
          ],
          'halve_cost'
        ),
      ]
    ),
    dc_action_add_keyword: actionSpec(
      'action.add_keyword',
      'Give keyword %1 to %2',
      [
        actionDropdown(
          'KEYWORD',
          KEYWORDS.map((value) => [value, value]),
          'keyword'
        ),
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_remove_keyword: actionSpec(
      'action.remove_keyword',
      'Remove keyword %1 from %2',
      [
        actionDropdown(
          'KEYWORD',
          KEYWORDS.map((value) => [value, value]),
          'keyword'
        ),
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_set_status: actionSpec(
      'action.set_status',
      'Set status %1 to %2 on %3',
      [
        actionDropdown(
          'STATUS',
          STATUSES.map((value) => [value, value]),
          'status_id'
        ),
        actionInput('VALUE', 'IntegerValue', 'value'),
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_remove_status: actionSpec(
      'action.remove_status',
      'Remove status %1 from %2',
      [
        actionDropdown(
          'STATUS',
          STATUSES.map((value) => [value, value]),
          'status_id'
        ),
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_silence: actionSpec(
      'action.silence',
      'Silence %1',
      [
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_paralyze: actionSpec(
      'action.paralyze',
      'Paralyze %1',
      [
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_remove_negative_effects: actionSpec(
      'action.remove_negative_effects',
      'Remove negative effects from %1',
      [
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_draw: actionSpec(
      'action.draw',
      'Draw %1 for %2',
      [
        actionInput('CARD', 'Selector', 'card'),
        actionInput('PLAYER', 'Selector', 'player'),
      ]
    ),
    dc_action_draw_next: actionSpec(
      'action.draw_next',
      '%1 draws the %2 card',
      [
        actionInput('PLAYER', 'Selector', 'player'),
        actionDropdown(
          'FROM_POS',
          [
            ['top', 'top'],
            ['bottom', 'bottom'],
          ],
          'from_pos'
        ),
      ]
    ),
    dc_action_draw_up_to: actionSpec(
      'action.draw_up_to',
      'Draw up to %1 Cards',
      [
        actionInput('COUNT', 'IntegerValue', 'count'),
      ]
    ),
    dc_action_take_fatigue_damage: actionSpec(
      'action.take_fatigue_damage',
      '%1 takes Fatigue DMG',
      [
        actionInput('PLAYER', 'Selector', 'player'),
      ]
    ),
    dc_action_move: actionSpec(
      'action.move',
      'Move %1 to %2 for %3',
      [
        actionInput('TARGET', 'Selector', 'target'),
        actionDropdown(
          'ZONE',
          [
            ['hand', 'HAND'],
            ['deck', 'DECK'],
          ],
          'zone'
        ),
        actionInput('CONTROLLER', 'Selector', 'controller'),
      ]
    ),
    dc_action_swap_cards: actionSpec(
      'action.swap_cards',
      'Swap %1 and %2',
      [
        actionInput('CARD1', 'Selector', 'card1'),
        actionInput('CARD2', 'Selector', 'card2'),
      ]
    ),
    dc_action_erase: actionSpec(
      'action.erase',
      'Erase %1',
      [
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_summon: actionSpec(
      'action.summon',
      'Summon %1 for %2 at %3',
      [
        actionInput('CARD', 'Selector', 'card'),
        actionInput('CONTROLLER', 'Selector', 'controller'),
        actionInput('SLOT', 'Selector', 'pos', true, 'position'),
      ]
    ),
    dc_action_cast: actionSpec(
      'action.cast',
      'Cast %1 for %2 at %3',
      [
        actionInput('CARD', 'Selector', 'card'),
        actionInput('CONTROLLER', 'Selector', 'controller'),
        actionInput('TARGET', 'Selector', 'effect_target'),
      ]
    ),
    dc_action_cast_random: actionSpec(
      'action.cast',
      'Cast %1 for %2 at a random target',
      [
        actionInput('CARD', 'Selector', 'card'),
        actionInput('CONTROLLER', 'Selector', 'controller'),
      ],
      {
        fixed: {
          effect_target: 'random',
        },
      }
    ),
    dc_action_fill_board: actionSpec(
      'action.fill_board',
      'Fill %1 board with %2',
      [
        actionInput('PLAYER', 'Selector', 'player'),
        actionInput('CARD', 'Selector', 'card'),
      ]
    ),
    dc_action_fill_hand: actionSpec(
      'action.fill_hand',
      'Fill %1 hand with %2',
      [
        actionInput('PLAYER', 'Selector', 'player'),
        actionInput('CARD', 'Selector', 'card'),
      ]
    ),
    dc_action_transform_card: actionSpec(
      'action.transform_card',
      'Turn %1 into %2',
      [
        actionInput('TARGET', 'Selector', 'target'),
        actionInput('NEW_CARD', 'Selector', 'new_card'),
      ]
    ),
    dc_action_catch: actionSpec(
      'action.catch',
      '%1 catches %2',
      [
        actionInput('CATCHER', 'Selector', 'catcher'),
        actionInput('CARD', 'Selector', 'card_to_catch'),
      ]
    ),
    dc_action_release_caught_card: actionSpec(
      'action.release_caught_card',
      'Release caught card from %1 into variable %2',
      [
        actionInput('CATCHER', 'Selector', 'catcher'),
        actionVariable('VARIABLE', 'var'),
      ],
      {
        customBlock: true,
      }
    ),
    dc_action_choose: actionSpec(
      'action.choose',
      'Ask %1 to choose one from %2',
      [
        actionInput('PLAYER', 'Selector', 'player'),
        actionInput('OPTIONS', 'Selector', 'options'),
      ]
    ),
    dc_action_set_player_hp: actionSpec(
      'action.set_player_hp',
      'Set %1 HP to %2',
      [
        actionInput('PLAYER', 'Selector', 'player'),
        actionInput('HP', 'IntegerValue', 'hp'),
      ]
    ),
    dc_action_earn_gold: actionSpec(
      'action.earn_gold',
      '%1 earns %2 gold',
      [
        actionInput('PLAYER', 'Selector', 'player'),
        actionInput('AMOUNT', 'IntegerValue', 'amount'),
      ]
    ),
    dc_action_spend_gold: actionSpec(
      'action.spend_gold',
      '%1 spends %2 gold',
      [
        actionInput('PLAYER', 'Selector', 'player'),
        actionInput('AMOUNT', 'IntegerValue', 'amount'),
      ]
    ),
    dc_action_set_gold: actionSpec(
      'action.set_gold',
      'Set %1 gold to %2',
      [
        actionInput('PLAYER', 'Selector', 'player'),
        actionInput('AMOUNT', 'IntegerValue', 'amount'),
      ]
    ),
    dc_action_skip_next_turn: actionSpec(
      'action.skip_next_turn',
      'Skip %1 next turn',
      [
        actionInput('PLAYER', 'Selector', 'player'),
      ]
    ),
    dc_action_trigger_ability: actionSpec(
      'action.trigger_ability',
      'Trigger %1 of %2',
      [
        actionDropdown('ABILITY', ENUM_VALUES.ability, 'ability'),
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_toggle_ability: actionSpec(
      'action.toggle_ability',
      '%1 %2 of %3',
      [
        actionBoolean('ENABLED', ENABLED_OPTIONS, 'enabled'),
        actionDropdown(
          'ABILITY',
          [
            ['Shock', 'SHOCK'],
            ['Support', 'SUPPORT'],
            ['Bullseye', 'BULLSEYE'],
            ['Program', 'PROGRAM'],
          ],
          'ability'
        ),
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_schedule_delay: actionSpec(
      'action.schedule_delay',
      'Trigger Delay of %1 at end of turn',
      [
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_add_artifact: actionSpec(
      'action.add_artifact',
      '%1 equip artifact named %2',
      [
        actionInput('PLAYER', 'Selector', 'player'),
        actionDefinition('NAME', 'artifact', 'artifact'),
      ]
    ),
    dc_action_toggle_artifact: actionSpec(
      'action.toggle_artifact',
      '%1 %2',
      [
        actionBoolean('ENABLED', ENABLED_OPTIONS, 'enabled'),
        actionInput('ARTIFACT', 'Selector', 'artifact'),
      ]
    ),
    dc_action_transform_artifact: actionSpec(
      'action.transform_artifact',
      'Turn %1 into artifact named %2',
      [
        actionInput('ARTIFACT', 'Selector', 'artifact'),
        actionDefinition('NAME', 'artifact', 'new_artifact'),
      ]
    ),
    dc_action_update_artifact_counter: actionSpec(
      'action.update_artifact_counter',
      'Change %1 counter by %2',
      [
        actionInput('ARTIFACT', 'Selector', 'artifact'),
        actionInput('DELTA', 'IntegerValue', 'delta'),
      ]
    ),
    dc_action_enchant: actionSpec(
      'action.enchant',
      'Enchant %1 with enchantment named %2',
      [
        actionInput('SLOT', 'Selector', 'slot'),
        actionDefinition('NAME', 'enchantment', 'enchantment'),
      ]
    ),
    dc_action_remove_enchantment: actionSpec(
      'action.remove_enchantment',
      'Remove %1',
      [
        actionInput('TARGET', 'Selector', 'target'),
      ]
    ),
    dc_action_transform_enchantment: actionSpec(
      'action.transform_enchantment',
      'Turn %1 into enchantment named %2',
      [
        actionInput('TARGET', 'Selector', 'target'),
        actionDefinition('NAME', 'enchantment', 'enchantment'),
      ]
    ),
    dc_action_update_enchantment_counter: actionSpec(
      'action.update_enchantment_counter',
      'Change %1 counter by %2',
      [
        actionInput('ENCHANTMENT', 'Selector', 'enchantment'),
        actionInput('DELTA', 'IntegerValue', 'delta'),
      ]
    ),
  };

  function defaultImplementation() {
    return {
      irVersion: 1,
      variables: [],
      targets: null,
      need: null,
      abilities: [],
      reactions: [],
    };
  }

  function loadScript(url) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = url;
      script.onload = resolve;
      script.onerror = () => reject(
        new Error(`Failed to load ${url}.`)
      );

      (document.head || document.documentElement).append(script);
    });
  }

  function parseExternalEditorText(text) {
    const source = text.trim();

    try {
      return JSON.parse(source);
    } catch (jsonError) {
      if (
        source.length === 0
        || source.length % 2 !== 0
        || !/^[0-9a-fA-F]+$/.test(source)
      ) {
        throw jsonError;
      }

      const bytes = new Uint8Array(source.length / 2);

      for (let index = 0; index < source.length; index += 2) {
        bytes[index / 2] = Number.parseInt(
          source.slice(index, index + 2),
          16
        );
      }

      const decoded = new TextDecoder(
        'utf-8',
        {fatal: true}
      ).decode(bytes);

      return JSON.parse(decoded);
    }
  }

  let blocklyPromise = null;

  function loadBlockly() {
    if (window.Blockly) {
      return Promise.resolve(window.Blockly);
    }

    if (blocklyPromise === null) {
      blocklyPromise = (async () => {
        await loadScript(`${BLOCKLY_BASE_URL}/blockly_compressed.js`);
        await loadScript(`${BLOCKLY_BASE_URL}/msg/en.js`);

        for (const url of BLOCKLY_PLUGIN_URLS) {
          await loadScript(url);
        }

        return window.Blockly;
      })();
    }

    return blocklyPromise;
  }

  let cardRendererPromise = null;

  function loadCardRenderer() {
    const rendererReady = () => (
      typeof window.appendCard === 'function'
      && typeof window.getResizedFontSize === 'function'
    );

    if (rendererReady()) {
      return Promise.resolve();
    }

    if (cardRendererPromise === null) {
      cardRendererPromise = Promise.resolve()
        .then(() => {
          if (typeof window.getResizedFontSize === 'function') {
            return undefined;
          }

          return loadScript(UNDERCARDS_HELPER_SCRIPT_URL);
        })
        .then(() => {
          if (typeof window.appendCard === 'function') {
            return undefined;
          }

          return loadScript(UNDERCARDS_CARD_SCRIPT_URL);
        })
        .then(() => {
          if (!rendererReady()) {
            throw new Error('Failed to load Undercards helper scripts.');
          }
        });
    }

    return cardRendererPromise;
  }

  function requestValue(request) {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  function transactionComplete(transaction) {
    return new Promise((resolve, reject) => {
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(
        transaction.error
        || new Error('IndexedDB transaction aborted.')
      );
    });
  }

  function openDatabase() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);

      request.onupgradeneeded = () => {
        const database = request.result;

        if (!database.objectStoreNames.contains('entities')) {
          const entities = database.createObjectStore(
            'entities',
            {
              keyPath: 'contentId',
            }
          );

          entities.createIndex(
            'importKey',
            'importKey',
            {
              unique: true,
            }
          );
        }

        if (!database.objectStoreNames.contains('assets')) {
          database.createObjectStore(
            'assets',
            {
              keyPath: 'assetId',
            }
          );
        }

        if (!database.objectStoreNames.contains('settings')) {
          database.createObjectStore(
            'settings',
            {
              keyPath: 'key',
            }
          );
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  function safeText(
    value,
    name,
    {
      minimum = 0,
      maximum,
    }
  ) {
    if (typeof value !== 'string') {
      throw new Error(`${name} must be a string.`);
    }

    const result = value.trim();

    if (
      result.length < minimum
      || result.length > maximum
    ) {
      throw new Error(
        `${name} must contain between ${minimum} and ${maximum} characters.`
      );
    }

    if (result.includes('<') || result.includes('>')) {
      throw new Error(`${name} cannot contain '<' or '>'.`);
    }

    return result;
  }

  function integer(
    value,
    name,
    minimum,
    maximum
  ) {
    if (
      !Number.isInteger(value)
      || value < minimum
      || value > maximum
    ) {
      throw new Error(
        `${name} must be an integer between ${minimum} and ${maximum}.`
      );
    }

    return value;
  }

  function unwrapCssUrl(raw, name) {
    if (typeof raw !== 'string') {
      throw new Error(`${name} must be an image reference.`);
    }

    let value = raw.trim();

    if (/^url\(/i.test(value)) {
      const match = value.match(
        /^url\(\s*(?:"([^"]*)"|'([^']*)'|([^"'()]+))\s*\)$/i
      );

      if (match === null) {
        throw new Error(`${name} contains an invalid CSS url().`);
      }

      value = (
        match[1]
        ?? match[2]
        ?? match[3]
      ).trim();
    }

    return value;
  }

  function externalEditorUrl(raw, name) {
    const value = unwrapCssUrl(raw, name);
    let url;

    try {
      url = new URL(value, EXTERNAL_EDITOR_ORIGIN);
    } catch {
      throw new Error(`${name} contains an invalid path.`);
    }

    const editorOrigin = new URL(EXTERNAL_EDITOR_ORIGIN).origin;

    if (
      url.protocol !== 'https:'
      || url.origin !== editorOrigin
    ) {
      throw new Error(
        `${name} must identify an existing asset.`
      );
    }

    return url;
  }

  function externalCardRarity(raw) {
    const url = externalEditorUrl(raw, 'Card rarity');

    let filename;

    try {
      filename = decodeURIComponent(
        url.pathname.split('/').pop() || ''
      );
    } catch {
      throw new Error('Card rarity contains an invalid filename.');
    }

    const match = filename.match(
      /^([A-Z][A-Z0-9]*)_([A-Z][A-Z0-9]*)\.png$/i
    );

    if (match === null) {
      throw new Error(
        `Could not read expansion and rarity from ${JSON.stringify(filename)}.`
      );
    }

    const extension = match[1].toUpperCase();
    const rarity = match[2].toUpperCase();

    if (extension !== 'BASE') {
      throw new Error(
        `Expansion ${JSON.stringify(extension)} is not supported.`
      );
    }

    if (!CARD_RARITIES.has(rarity)) {
      throw new Error(
        `Card rarity ${JSON.stringify(rarity)} is not supported.`
      );
    }

    return rarity;
  }

  function normalizeExternalImage(raw, name, kind) {
    if (raw === null || raw === undefined) {
      return null;
    }

    const value = unwrapCssUrl(raw, name);

    if (value.startsWith('data:')) {
      const match = value.match(
        /^data:(image\/(?:png|jpeg|webp|gif));base64,([A-Za-z0-9+/]*={0,2})$/i
      );

      if (match === null) {
        throw new Error(`${name} must be an image data URL.`);
      }

      const mimeType = match[1].toLowerCase();
      const base64 = match[2];
      const padding = base64.endsWith('==')
        ? 2
        : base64.endsWith('=')
          ? 1
          : 0;
      const size = Math.floor(base64.length * 3 / 4) - padding;

      if (size <= 0 || size > MAX_IMAGE_BYTES) {
        throw new Error(
          `${name} must be nonempty and no larger than 5 MiB.`
        );
      }

      return {
        kind: 'data',
        mimeType,
        data: base64,
      };
    }

    const url = externalEditorUrl(value, name);
    const prefix = (
      kind === 'artifact'
        ? '/images/artifacts/'
        : '/images/cards/'
    );

    let pathname;

    try {
      pathname = decodeURIComponent(url.pathname);
    } catch {
      throw new Error(`${name} contains an invalid filename.`);
    }

    if (!pathname.startsWith(prefix)) {
      throw new Error(
        `${name} does not identify a supported existing image.`
      );
    }

    const filename = pathname.slice(prefix.length);
    const match = filename.match(
      /^([A-Za-z0-9][A-Za-z0-9_-]{0,127})\.png$/i
    );

    if (match === null) {
      throw new Error(
        `${name} does not identify a supported existing image.`
      );
    }

    return {
      kind: 'existing',
      name: match[1],
    };
  }

  function normalizedEnumName(value, name) {
    if (typeof value !== 'string') {
      throw new Error(`${name} must be a name.`);
    }

    return value
      .trim()
      .toUpperCase()
      .replace(/[\s-]+/g, '_');
  }

  function normalizedTribes(raw, name) {
    if (!Array.isArray(raw)) {
      throw new Error(`${name} must be an array.`);
    }

    const result = [];

    raw.forEach((entry, index) => {
      let value = entry;

      if (
        entry
        && typeof entry === 'object'
        && !Array.isArray(entry)
      ) {
        if (entry.custom === true) {
          throw new Error(
            `${name}[${index}] uses an unsupported custom Tribe.`
          );
        }

        value = entry.name;
      }

      const tribe = normalizedEnumName(
        value,
        `${name}[${index}]`
      );

      if (!TRIBES.has(tribe)) {
        throw new Error(
          `${name}[${index}] uses unknown Tribe ${JSON.stringify(tribe)}.`
        );
      }

      if (!result.includes(tribe)) {
        result.push(tribe);
      }
    });

    return result;
  }

  function normalizedPowers(raw, name) {
    if (raw === null || raw === undefined) {
      return {
        keywords: [],
        statuses: {},
      };
    }

    if (!Array.isArray(raw)) {
      throw new Error(`${name} must be an array.`);
    }

    const keywordAliases = {
      charge: 'CHARGE',
      haste: 'HASTE',
      taunt: 'TAUNT',
      kr: 'KR',
      candy: 'CANDY',
      armor: 'ARMOR',
      transparency: 'TRANSPARENCY',
      disarmed: 'DISARMED',
      invulnerable: 'INVULNERABLE',
      silence: 'SILENCED',
      silenced: 'SILENCED',
      wanted: 'WANTED',
      darkspawn: 'DARKSPAWN',
      flowerypower: 'FLOWERY_POWER',
    };
    const statusAliases = {
      paralyzed: 'PARALYZED',
      dodge: 'DODGE',
      loop: 'LOOP',
    };
    const keywords = [];
    const statuses = {};

    raw.forEach((power, index) => {
      if (
        !power
        || typeof power !== 'object'
        || Array.isArray(power)
      ) {
        throw new Error(`${name}[${index}] must be an object.`);
      }

      if (power.custom === true) {
        throw new Error(
          `${name}[${index}] uses an unsupported custom power.`
        );
      }

      const rawPowerName = safeText(
        power.name,
        `${name}[${index}].name`,
        {
          minimum: 1,
          maximum: 64,
        }
      );
      const key = rawPowerName
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '');

      const keyword = keywordAliases[key];
      if (keyword !== undefined) {
        if (
          power.counter !== false
          && power.counter !== null
          && power.counter !== undefined
        ) {
          throw new Error(
            `${name}[${index}] gives a counter to non-counter keyword ${JSON.stringify(rawPowerName)}.`
          );
        }

        if (!keywords.includes(keyword)) {
          keywords.push(keyword);
        }
        return;
      }

      const status = statusAliases[key];
      if (status !== undefined) {
        if (Object.prototype.hasOwnProperty.call(statuses, status)) {
          throw new Error(
            `${name} contains ${JSON.stringify(rawPowerName)} more than once.`
          );
        }

        statuses[status] = (
          power.counter === false
          || power.counter === null
          || power.counter === undefined
        )
          ? 1
          : integer(
              power.counter,
              `${name}[${index}].counter`,
              1,
              999
            );
        return;
      }

      throw new Error(
        `${name}[${index}] uses unknown power ${JSON.stringify(rawPowerName)}.`
      );
    });

    return {
      keywords,
      statuses,
    };
  }

  function assertNoEntityPowers(powers, name) {
    if (
      powers.keywords.length !== 0
      || Object.keys(powers.statuses).length !== 0
    ) {
      throw new Error(
        `${name} are only supported for monsters and spells.`
      );
    }
  }

  function normalizeExternalCard(card, index) {
    if (
      !card
      || typeof card !== 'object'
      || Array.isArray(card)
    ) {
      throw new Error(`cards[${index}] must be an object.`);
    }

    if (
      typeof card.id !== 'string'
      && typeof card.id !== 'number'
    ) {
      throw new Error(`cards[${index}].id is required.`);
    }

    const externalId = String(card.id).trim();

    if (externalId.length === 0) {
      throw new Error(`cards[${index}].id cannot be empty.`);
    }

    const kinds = {
      0: 'monster',
      1: 'spell',
      99: 'enchantment',
    };
    const kind = kinds[card.cardType];

    if (kind === undefined) {
      throw new Error(
        `cards[${index}] uses unsupported cardType ${String(card.cardType)}.`
      );
    }

    const name = safeText(
      card.name,
      `cards[${index}].name`,
      {
        minimum: 1,
        maximum: 100,
      }
    );

    const description = safeText(
      card.desc ?? '',
      `cards[${index}].desc`,
      {
        maximum: 1000,
      }
    );

    if (card.isRarityCustom === true) {
      throw new Error(
        `cards[${index}] uses an unsupported custom rarity.`
      );
    }

    const image = normalizeExternalImage(
      card.image,
      `cards[${index}].image`,
      kind
    );
    const powers = normalizedPowers(
      card.powers,
      `cards[${index}].powers`
    );

    if (kind === 'monster') {
      if (
        !Array.isArray(card.stats)
        || card.stats.length !== 3
      ) {
        throw new Error(
          `cards[${index}].stats must be [cost, attack, hp].`
        );
      }

      return {
        importKey: `card:${externalId}`,
        kind,
        image,
        definition: {
          name,
          description,
          rarity: externalCardRarity(card.rarity),
          cost: integer(
            card.stats[0],
            `cards[${index}].stats[0]`,
            0,
            999
          ),
          attack: integer(
            card.stats[1],
            `cards[${index}].stats[1]`,
            0,
            999
          ),
          hp: integer(
            card.stats[2],
            `cards[${index}].stats[2]`,
            1,
            999
          ),
          tribes: normalizedTribes(
            card.tribes ?? [],
            `cards[${index}].tribes`
          ),
          keywords: powers.keywords,
          statuses: powers.statuses,
        },
      };
    }

    if (kind === 'spell') {
      const rarity = externalCardRarity(card.rarity);
      let soulId;

      if (
        card.spellSoul === null
        || card.spellSoul === undefined
      ) {
        soulId = rarity === 'TOKEN' ? null : 'KINDNESS';
      } else {
        soulId = safeText(
          card.spellSoul,
          `cards[${index}].spellSoul`,
          {
            minimum: 1,
            maximum: 32,
          }
        ).toUpperCase();

        if (!STANDARD_SOULS.includes(soulId)) {
          throw new Error(
            `cards[${index}] uses unknown SOUL ${JSON.stringify(soulId)}.`
          );
        }
      }

      return {
        importKey: `card:${externalId}`,
        kind,
        image,
        definition: {
          name,
          description,
          rarity,
          cost: integer(
            card.stats,
            `cards[${index}].stats`,
            0,
            999
          ),
          keywords: powers.keywords,
          statuses: powers.statuses,
          soulId,
        },
      };
    }

    assertNoEntityPowers(
      powers,
      `cards[${index}].powers`
    );

    return {
      importKey: `enchantment:${externalId}`,
      kind,
      image,
      definition: {
        name,
        description,
        initialCounter: 0,
      },
    };
  }

  function normalizeExternalArtifact(artifact, index) {
    if (
      !artifact
      || typeof artifact !== 'object'
      || Array.isArray(artifact)
    ) {
      throw new Error(
        `artifacts[${index}] must be an object.`
      );
    }

    const name = safeText(
      artifact.name,
      `artifacts[${index}].name`,
      {
        minimum: 1,
        maximum: 100,
      }
    );

    const rarity = safeText(
      artifact.rarity,
      `artifacts[${index}].rarity`,
      {
        minimum: 1,
        maximum: 32,
      }
    ).toUpperCase();

    if (!ARTIFACT_RARITIES.has(rarity)) {
      throw new Error(
        `artifacts[${index}] uses unsupported rarity ${JSON.stringify(rarity)}.`
      );
    }

    return {
      importKey: `artifact:${name.toLowerCase()}`,
      kind: 'artifact',
      image: normalizeExternalImage(
        artifact.image,
        `artifacts[${index}].image`,
        'artifact'
      ),
      definition: {
        name,
        description: safeText(
          artifact.desc ?? '',
          `artifacts[${index}].desc`,
          {
            maximum: 1000,
          }
        ),
        rarity,
        initialCounter: 0,
      },
    };
  }

  function normalizeExternalExport(raw) {
    const errors = [];
    const drafts = [];

    if (
      !raw
      || typeof raw !== 'object'
      || Array.isArray(raw)
    ) {
      return {
        name: null,
        drafts,
        errors: ['The imported JSON root must be an object.'],
      };
    }

    let name = null;

    if (raw.name !== undefined) {
      try {
        name = safeText(
          raw.name,
          'name',
          {
            minimum: 1,
            maximum: 100,
          }
        );
      } catch (error) {
        errors.push(error.message);
      }
    }

    if (!Array.isArray(raw.cards)) {
      errors.push('cards must be an array.');
    } else {
      raw.cards.forEach((card, index) => {
        try {
          drafts.push(
            normalizeExternalCard(card, index)
          );
        } catch (error) {
          errors.push(error.message);
        }
      });
    }

    const artifacts = raw.artifacts ?? [];

    if (!Array.isArray(artifacts)) {
      errors.push('artifacts must be an array.');
    } else {
      artifacts.forEach((artifact, index) => {
        try {
          drafts.push(
            normalizeExternalArtifact(artifact, index)
          );
        } catch (error) {
          errors.push(error.message);
        }
      });
    }

    const seen = new Set();

    for (const draft of drafts) {
      if (seen.has(draft.importKey)) {
        errors.push(
          `The import contains duplicate identity ${JSON.stringify(draft.importKey)}.`
        );
      }

      seen.add(draft.importKey);
    }

    return {
      name,
      drafts,
      errors,
    };
  }

  async function jsonRequest(url, options = {}) {
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.error?.message || `Got HTTP ${response.status}.`
        );
      }

      return result;

    } catch (error) {
      alert('Request failed. Check that the correct Game Server is selected in the plugin settings.');
      throw error;
    }
  }

  async function validateImageBlob(blob) {
    if (
      !(blob instanceof Blob)
      || blob.size === 0
      || blob.size > MAX_IMAGE_BYTES
    ) {
      throw new Error(
        'Images must be nonempty and no larger than 5 MiB.'
      );
    }

    const bitmap = await createImageBitmap(blob);
    bitmap.close();
  }

  function blobFromBase64(base64, mimeType) {
    const decoded = atob(base64);
    const bytes = new Uint8Array(decoded.length);

    for (let index = 0; index < decoded.length; index++) {
      bytes[index] = decoded.charCodeAt(index);
    }

    return new Blob(
      [bytes],
      {
        type: mimeType,
      }
    );
  }

  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = () => {
        const dataUrl = String(reader.result);
        resolve(
          dataUrl.slice(dataUrl.indexOf(',') + 1)
        );
      };

      reader.onerror = () => reject(
        reader.error
        || new Error('Could not read an image.')
      );

      reader.readAsDataURL(blob);
    });
  }

  async function blobFromDataImage(image) {
    let blob;

    try {
      blob = blobFromBase64(
        image.data,
        image.mimeType
      );
    } catch {
      throw new Error('The imported image contains invalid base64 data.');
    }

    await validateImageBlob(blob);
    return blob;
  }

  function element(tagName, options = {}, ...children) {
    const result = document.createElement(tagName);

    if (options.className) {
      result.className = options.className;
    }

    if (options.text !== undefined) {
      result.textContent = String(options.text);
    }

    if (options.type) {
      result.type = options.type;
    }

    if (options.value !== undefined) {
      result.value = options.value;
    }

    if (options.accept) {
      result.accept = options.accept;
    }

    if (options.placeholder) {
      result.placeholder = options.placeholder;
    }

    if (options.disabled) {
      result.disabled = true;
    }

    for (const child of children.flat()) {
      if (child === null || child === undefined) {
        continue;
      }

      result.append(
        child instanceof Node
          ? child
          : document.createTextNode(String(child))
      );
    }

    return result;
  }

  function actionButton(label, callback, disabled = false) {
    const button = element('button', {
      type: 'button',
      className: 'dc-editor-button',
      text: label,
      disabled,
    });

    button.addEventListener('click', callback);
    return button;
  }

  function downloadJson(filename, value) {
    const blob = new Blob(
      [JSON.stringify(value, null, 2)],
      {
        type: 'application/json',
      }
    );
    const url = URL.createObjectURL(blob);
    const anchor = element('a');

    anchor.href = url;
    anchor.download = filename;
    anchor.click();

    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function setEditorCardText(target, value, format) {
    const text = String(value);

    if (format && text.includes('{{')) {
      target.innerHTML = window.jQuery.i18n(
        text.replace('<', '&lt;').replace('>', '&gt;')
      );
    } else {
      target.textContent = text;
    }
  }

  function entityKindForBlock(block) {
    const workspace = block.workspace;

    return (
      workspace.dcEntityKind
      ?? workspace.targetWorkspace?.dcEntityKind
      ?? workspace.options?.parentWorkspace?.dcEntityKind
      ?? null
    );
  }

  function abilityOptions(block) {
    const abilities = ROOT_CONFIG[
      entityKindForBlock(block)
    ]?.abilities;

    const choices = (
      Array.isArray(abilities) && abilities.length > 0
        ? abilities
        : ALL_ABILITIES
    );

    return choices.map((ability) => [
      ABILITY_LABELS[ability] || ability,
      ability,
    ]);
  }

  function attributeOutputChecks(attribute) {
    if (INTEGER_ATTRIBUTES.has(attribute)) {
      return ['Value', 'IntegerValue'];
    }

    if (ENUM_ATTRIBUTES.has(attribute)) {
      return ['Value', 'EnumValue'];
    }

    return ['Value'];
  }

  function eventValueOutputChecks(field) {
    if (INTEGER_EVENT_FIELDS.has(field)) {
      return ['Value', 'IntegerValue'];
    }

    if (BOOLEAN_EVENT_FIELDS.has(field)) {
      return ['Value', 'Condition'];
    }

    if (ENUM_EVENT_FIELDS.has(field)) {
      return ['Value', 'EnumValue'];
    }

    return ['Value'];
  }

  function enumOutputChecks(enumName) {
    const checks = ['Value', 'EnumValue'];

    if (enumName === 'tribe') {
      checks.push('TribeValue');
    }

    return checks;
  }

  const BLOCKLY_DYNAMIC_RESTORE_FLAG =
    'deltacardsRestoringDynamicState';
  const BLOCKLY_RESTORED_FIELD_VALUES =
    'deltacardsRestoredFieldValues';
  const BLOCKLY_DYNAMIC_OUTPUT_REFRESH =
    'deltacardsRefreshOutputChecks';

  function isRestoringBlocklyDynamicState(workspace) {
    return workspace?.[BLOCKLY_DYNAMIC_RESTORE_FLAG] === true;
  }

  function normalizedConnectionChecks(checks) {
    if (checks === null || checks === undefined) {
      return null;
    }

    return Array.isArray(checks)
      ? checks
      : [checks];
  }

  function connectionChecksEqual(left, right) {
    const leftChecks = normalizedConnectionChecks(left);
    const rightChecks = normalizedConnectionChecks(right);

    if (
      leftChecks === null
      || rightChecks === null
    ) {
      return leftChecks === rightChecks;
    }

    return (
      leftChecks.length === rightChecks.length
      && leftChecks.every((check) => (
        rightChecks.includes(check)
      ))
    );
  }

  function setDynamicOutputChecks(block, checks) {
    const connection = block.outputConnection;

    if (!connection) {
      return false;
    }

    if (
      connectionChecksEqual(
        connection.getCheck(),
        checks
      )
    ) {
      return false;
    }

    connection.setCheck(checks);
    return true;
  }

  function collectSerializedFieldValues(
    serializedWorkspace
  ) {
    const result = new Map();

    const visit = (value) => {
      if (
        value === null
        || typeof value !== 'object'
      ) {
        return;
      }

      if (
        typeof value.id === 'string'
        && value.fields
        && typeof value.fields === 'object'
        && !Array.isArray(value.fields)
      ) {
        result.set(value.id, value.fields);
      }

      for (const child of Object.values(value)) {
        visit(child);
      }
    };

    visit(serializedWorkspace);
    return result;
  }

  function dropdownOptionsForRestore(
    block,
    fieldName,
    options
  ) {
    if (!isRestoringBlocklyDynamicState(block.workspace)) {
      return options;
    }

    const restoredFields = block.workspace?.[
      BLOCKLY_RESTORED_FIELD_VALUES
    ]?.get(block.id);
    const savedValue = restoredFields?.[fieldName];

    if (
      typeof savedValue !== 'string'
      || options.some(([, value]) => value === savedValue)
    ) {
      return options;
    }

    return [
      ...options,
      [savedValue, savedValue],
    ];
  }

  function installDynamicOutputChecks(
    block,
    {
      fields = [],
      resolve,
    }
  ) {
    const refresh = (overrides = null) => {
      // Blockly can attempt connections before all serialized fields,
      // ancestors, and children have been restored. A null check means
      // "accept any type" only during that short restore phase.
      const checks = isRestoringBlocklyDynamicState(
        block.workspace
      )
        ? null
        : resolve((fieldName) => {
            if (
              overrides !== null
              && Object.prototype.hasOwnProperty.call(
                overrides,
                fieldName
              )
            ) {
              return overrides[fieldName];
            }

            return block.getFieldValue(fieldName);
          });

      return setDynamicOutputChecks(block, checks);
    };

    block[BLOCKLY_DYNAMIC_OUTPUT_REFRESH] = () => (
      refresh()
    );

    for (const fieldName of fields) {
      const field = block.getField(fieldName);

      if (field === null) {
        continue;
      }

      const previousValidator =
        field.getValidator?.() ?? null;

      field.setValidator((value) => {
        const validatedValue = (
          typeof previousValidator === 'function'
            ? previousValidator.call(field, value)
            : value
        );

        if (
          validatedValue !== null
          && validatedValue !== undefined
        ) {
          // Field.setValue has not necessarily committed the new value
          // yet, so resolve with the proposed value explicitly.
          refresh({
            [fieldName]: validatedValue,
          });
        }

        return validatedValue;
      });
    }

    block.setOnChange(() => {
      refresh();
    });

    refresh();
  }

  function refreshDynamicOutputChecks(workspace) {
    if (isRestoringBlocklyDynamicState(workspace)) {
      return;
    }

    const blocks = workspace.getAllBlocks(false);
    const maximumPasses = Math.max(1, blocks.length + 1);

    // Some output types depend on another dynamic output type. For example:
    // attribute -> unique values -> for-each variable -> variable reference.
    // Re-evaluate until the checks stop changing.
    for (let pass = 0; pass < maximumPasses; pass++) {
      let changed = false;

      for (const block of blocks) {
        const refresh = block[
          BLOCKLY_DYNAMIC_OUTPUT_REFRESH
        ];

        if (typeof refresh === 'function') {
          changed = refresh() || changed;
        }
      }

      if (!changed) {
        return;
      }
    }
  }

  function restoreBlocklyWorkspace(
    workspace,
    serializedWorkspace
  ) {
    workspace[BLOCKLY_DYNAMIC_RESTORE_FLAG] = true;

    try {
      workspace[BLOCKLY_RESTORED_FIELD_VALUES] =
        collectSerializedFieldValues(
          serializedWorkspace
        );

        window.Blockly.serialization.workspaces.load(
          serializedWorkspace,
          workspace
        );
    } finally {
      delete workspace[BLOCKLY_DYNAMIC_RESTORE_FLAG];
      delete workspace[BLOCKLY_RESTORED_FIELD_VALUES];
    }

    refreshDynamicOutputChecks(workspace);
  }

  function enclosingReaction(block) {
    const root = block.getRootBlock();
    return root?.type === 'dc_reaction' ? root : null;
  }

  function eventDetailOptions(block, kind) {
    const event = enclosingReaction(block)?.getFieldValue('EVENT');
    const values = EVENT_DETAILS[event]?.[kind]
      ?? Object.values(EVENT_DETAILS)
        .flatMap((entry) => entry[kind]);

    const unique = [...new Set(values)];
    return unique.length === 0
      ? [['not available', '']]
      : unique.map((value) => [
          value.replaceAll('_', ' '),
          value,
        ]);
  }

  function forEachVariableType(block) {
    const iterable = block.getInputTargetBlock('ITERABLE');
    const checks = iterable?.outputConnection?.getCheck() || [];

    if (checks.includes('IntegerList')) return 'integer';
    if (checks.includes('TribeList')) return 'tribe';
    if (checks.includes('ValueList')) return 'value';

    return 'selector';
  }

  function childInputName(block, ancestor) {
    let child = block;

    while (
      child.getParent() !== null
      && child.getParent() !== ancestor
    ) {
      child = child.getParent();
    }

    return ancestor.inputList.find(
      (input) => input.connection?.targetBlock() === child
    )?.name ?? null;
  }

  function visibleVariables(block) {
    const definitions = new Map();

    for (const topBlock of block.workspace.getTopBlocks(false)) {
      if (topBlock.type !== 'dc_variable_declaration') continue;

      const name = topBlock.getFieldValue('NAME').trim();
      if (name) {
        definitions.set(name, topBlock.getFieldValue('TYPE'));
      }
    }

    let ancestor = block.getSurroundParent();
    while (ancestor !== null) {
      const inputName = childInputName(block, ancestor);

      if (
        ancestor.type === 'dc_effect_for'
        && inputName === 'EFFECT'
      ) {
        const name = ancestor
          .getFieldValue('INDEX_VARIABLE')
          .trim();

        if (name) definitions.set(name, 'integer');
      }

      if (
        ancestor.type === 'dc_effect_for_each'
        && inputName === 'EFFECT'
      ) {
        const name = ancestor
          .getFieldValue('VARIABLE')
          .trim();

        if (name) {
          definitions.set(
            name,
            forEachVariableType(ancestor)
          );
        }

        const indexName = ancestor
          .getFieldValue('INDEX_VARIABLE')
          .trim();

        if (indexName) {
          definitions.set(indexName, 'integer');
        }
      }

      ancestor = ancestor.getSurroundParent();
    }

    return definitions;
  }

  function variableOutputChecks(type) {
    const checks = {
      selector: ['Selector'],
      integer: ['Value', 'IntegerValue'],
      boolean: ['Value', 'Condition'],
      result: ['ActionResult'],
      tribe: ['Value', 'EnumValue', 'TribeValue'],
      value: ['Value'],
    };

    return checks[type] || ['Value'];
  }

  function variableOptions(block, requiredType = null) {
    const options = [...visibleVariables(block)]
      .filter(([, type]) => requiredType === null || type === requiredType)
      .map(([name]) => [name, name]);

    const choices = (
      options.length === 0
        ? [['no variable', '']]
        : options
    );

    // During restore, an otherwise valid variable can be unavailable until
    // its declaration or enclosing loop has been connected.
    if (
      isRestoringBlocklyDynamicState(block.workspace)
      && !choices.some(([, value]) => value === '')
    ) {
      choices.unshift(['no variable', '']);
    }

    return dropdownOptionsForRestore(
      block,
      'VARIABLE',
      choices
    );
  }

  function blockValueInput(name, check) {
    return {
      type: 'input_value',
      name,
      check,
    };
  }

  function blockStatementInput(name, check = 'Effect') {
    return {
      type: 'input_statement',
      name,
      check,
    };
  }

  function blockDropdown(name, options) {
    return {
      type: 'field_dropdown',
      name,
      options,
    };
  }

  function blockText(name, text = '') {
    return {
      type: 'field_input',
      name,
      text,
    };
  }

  function outputBlock(
    type,
    message0,
    args0,
    output,
    colour,
    extra = {}
  ) {
    return {
      type,
      message0,
      args0,
      output,
      colour,
      ...extra,
    };
  }

  function statementBlock(
    type,
    message0,
    args0,
    colour = 20
  ) {
    return {
      type,
      message0,
      args0,
      inputsInline: true,
      previousStatement: 'Effect',
      nextStatement: 'Effect',
      colour,
    };
  }

  function actionArgumentJson(argument) {
    if (argument.type === 'input') {
      return blockValueInput(argument.name, argument.check);
    }

    if (
      argument.type === 'dropdown'
      || argument.type === 'boolean'
    ) {
      return blockDropdown(argument.name, argument.options);
    }

    if (argument.type === 'definition') {
      return blockText(argument.name);
    }

    throw new Error(
      `Action argument ${argument.name} requires a custom block.`
    );
  }

  function actionBlockJson(type, spec) {
    return statementBlock(
      type,
      spec.message,
      spec.args.map(actionArgumentJson)
    );
  }

  function registerBlocklyBlocks() {
    const Blockly = window.Blockly;

    if (!Blockly) {
      throw new Error('Blockly was not loaded.');
    }

    if (Blockly.Blocks.dc_root_monster) {
      return;
    }

    for (
      const [kind, config]
      of Object.entries(ROOT_CONFIG)
    ) {
      Blockly.Blocks[config.block] = {
        init() {
          this.appendDummyInput()
            .appendField(kind);

          if (config.targets) {
            this.appendValueInput('TARGETS')
              .setCheck('Selector')
              .appendField('Play targets');
          }

          if (config.need) {
            this.appendValueInput('NEED')
              .setCheck([
                'Condition',
                'Selector',
              ])
              .appendField('Need');
          }

          this.setColour(290);
          this.setDeletable(false);
          this.setMovable(false);
        },
      };
    }

    Blockly.defineBlocksWithJsonArray([
      ...Object.entries(SIMPLE_EXPRESSIONS).map(
        ([type, spec]) => ({
          type,
          message0: spec.label,
          output: spec.output,
          colour: spec.colour,
        })
      ),
      {
        type: 'dc_variable_declaration',
        message0: 'Variable %1 type %2',
        args0: [
          blockText('NAME', 'value'),
          blockDropdown('TYPE', [
            ['selector', 'selector'],
            ['integer', 'integer'],
            ['boolean', 'boolean'],
            ['action result', 'result'],
          ]),
        ],
        colour: 330,
      },
      {
        type: 'dc_reaction',
        message0: 'After %1',
        args0: [
          blockDropdown('EVENT', EVENT_OPTIONS),
        ],
        message1: 'when %1',
        args1: [
          blockValueInput(
            'CONDITION',
            ['Condition', 'Selector']
          ),
        ],
        nextStatement: 'Effect',
        colour: 290,
      },

      outputBlock(
        'dc_selector_zone',
        'cards in %1\'s %2',
        [
          blockValueInput('PLAYER', 'Selector'),
          blockDropdown('ZONE', [
            ['board', 'BOARD'],
            ['hand', 'HAND'],
            ['deck', 'DECK'],
            ['dustpile', 'DUSTPILE'],
            ['erased', 'ERASED'],
          ]),
        ],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_controller_of',
        'controller of %1',
        [blockValueInput('SELECTOR', 'Selector')],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_opponent_of',
        'opponent of %1',
        [blockValueInput('SELECTOR', 'Selector')],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_named',
        '%1 named %2',
        [
          blockDropdown('KIND', [
            ['card', 'card'],
            ['artifact', 'artifact'],
            ['enchantment', 'enchantment'],
          ]),
          blockText('NAME'),
        ],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_artifact_of_player',
        '%1\'s equipped artifact named %2',
        [
          blockValueInput('PLAYER', 'Selector'),
          blockText('NAME'),
        ],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_board_slots_of',
        'board slots of %1',
        [blockValueInput('PLAYER', 'Selector')],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_enchantments_of',
        'enchantments of %1',
        [blockValueInput('PLAYER', 'Selector')],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_relative_board',
        'monster(s) %1 %2',
        [
          blockDropdown('RELATION', [
            ['left of', 'left'],
            ['right of', 'right'],
            ['adjacent to', 'adjacent'],
            ['in front of', 'front'],
            ['anywhere left of', 'left_of'],
            ['anywhere right of', 'right_of'],
          ]),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_relative_hand',
        'card(s) %1 %2 in hand',
        [
          blockDropdown('RELATION', [
            ['left of', 'left'],
            ['right of', 'right'],
            ['adjacent to', 'adjacent'],
            ['anywhere left of', 'left_of'],
            ['anywhere right of', 'right_of'],
          ]),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_slot_of',
        'board slots of %1',
        [blockValueInput('SELECTOR', 'Selector')],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_slot_content',
        '%1 in %2',
        [
          blockDropdown('KIND', [
            ['monster', 'monster'],
            ['enchantment', 'enchantment'],
          ]),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Selector',
        210
      ),
      outputBlock(
        'dc_selector_combine',
        '%1 %2 %3',
        [
          blockValueInput('LEFT', 'Selector'),
          blockDropdown('OPERATION', [
            ['combined with', 'union'],
            ['intersected with', 'intersection'],
            ['without', 'difference'],
          ]),
          blockValueInput('RIGHT', 'Selector'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_index',
        'item %1 of %2',
        [
          blockValueInput('INDEX', 'IntegerValue'),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_take',
        '%1 %2 of %3',
        [
          blockDropdown('SIDE', [
            ['first', 'first'],
            ['last', 'last'],
          ]),
          blockValueInput('COUNT', 'IntegerValue'),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_left_rightmost',
        '%1 Monster from %2',
        [
          blockDropdown('SIDE', [
            ['leftmost', 'left'],
            ['rightmost', 'right'],
          ]),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_limit_per',
        'keep at most %1 per %2 in %3',
        [
          blockValueInput('COUNT', 'IntegerValue'),
          blockValueInput('KEY', 'Value'),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_copy',
        'create %1 copy of %2',
        [
          blockDropdown('MODE', [
            ['a', 'copy'],
            ['an exact', 'exact_copy'],
          ]),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_random',
        'choose %1 at random from %2',
        [
          blockValueInput('COUNT', 'IntegerValue'),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_minmax',
        '%1 %2 from %3 by %4',
        [
          blockDropdown('MODE', [
            ['lowest', 'min'],
            ['highest', 'max'],
          ]),
          blockValueInput('COUNT', 'IntegerValue'),
          blockValueInput('SELECTOR', 'Selector'),
          blockValueInput('KEY', 'Value'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_sort',
        'sort %1 by %2 %3',
        [
          blockValueInput('SELECTOR', 'Selector'),
          blockValueInput('KEY', 'Value'),
          blockDropdown('DIRECTION', [
            ['ascending', 'ascending'],
            ['descending', 'descending'],
          ]),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_distinct',
        'different items in %1 by %2',
        [
          blockValueInput('SELECTOR', 'Selector'),
          blockValueInput('KEY', 'Value'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_generate',
        'generate %1 copies of %2 for %3',
        [
          blockValueInput('COUNT', 'IntegerValue'),
          blockValueInput('SELECTOR', 'Selector'),
          blockValueInput('CONTROLLER', 'Selector'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_discover',
        'discover %1 cards matching %2 for %3',
        [
          blockValueInput('COUNT', 'IntegerValue'),
          blockValueInput('PREDICATE', 'CandidatePredicate'),
          blockValueInput('CONTROLLER', 'Selector'),
        ],
        'Selector',
        180
      ),
      outputBlock(
        'dc_selector_filter',
        'from %1, keep only those that %2',
        [
          blockValueInput('SELECTOR', 'Selector'),
          blockValueInput('PREDICATE', 'CandidatePredicate'),
        ],
        'Selector',
        210
      ),

      outputBlock(
        'dc_predicate_card_type',
        'is a %1',
        [
          blockDropdown('TYPE', [
            ['monster', 'monster'],
            ['spell', 'spell'],
          ]),
        ],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_has_ability',
        'has ability %1',
        [blockDropdown('ABILITY', ABILITY_OPTIONS)],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_has_keyword',
        'has keyword %1',
        [
          blockDropdown(
            'KEYWORD',
            KEYWORDS.map((value) => [value, value])
          ),
        ],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_has_status',
        'has status %1',
        [
          blockDropdown(
            'STATUS',
            STATUSES.map((value) => [value, value])
          ),
        ],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_has_tribe',
        'has Tribe %1',
        [blockDropdown('TRIBE', ENUM_VALUES.tribe)],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_expansion',
        'has expansion %1',
        [blockDropdown('EXPANSION', ENUM_VALUES.expansion)],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_rarity',
        'rarity %1 %2',
        [
          blockDropdown('OPERATOR', COMPARISON_OPTIONS),
          blockDropdown(
            'RARITY',
            [...CARD_RARITIES].map((value) => [value, value])
          ),
        ],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_generated',
        'is %1',
        [
          blockDropdown('GENERATED', [
            ['generated', 'true'],
            ['not generated', 'false'],
          ]),
        ],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_generated_by',
        'was generated by %1',
        [blockValueInput('CREATOR', 'Selector')],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_slot_state',
        'slot is %1',
        [
          blockDropdown('STATE', [
            ['empty', 'empty'],
            ['occupied', 'occupied'],
            ['enchanted', 'enchanted'],
            ['unenchanted', 'unenchanted'],
          ]),
        ],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_slot_has_enchantment',
        'slot has enchantment named %1',
        [blockText('NAME')],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_has_artifact',
        '%1 has artifact named %2',
        [
          blockValueInput('PLAYER', 'Selector'),
          blockText('NAME'),
        ],
        ['Selector', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_attribute_compare',
        '%1 %2 %3',
        [
          blockDropdown('ATTRIBUTE', ATTRIBUTE_OPTIONS),
          blockDropdown('OPERATOR', COMPARISON_OPTIONS),
          blockValueInput('VALUE', 'Value'),
        ],
        'CandidatePredicate',
        120
      ),
      outputBlock(
        'dc_predicate_compare',
        'Compare %1 %2 %3',
        [
          blockValueInput('LEFT', 'Value'),
          blockDropdown('OPERATOR', COMPARISON_OPTIONS),
          blockValueInput('RIGHT', 'Value'),
        ],
        'Condition',
        120,
        {
          inputsInline: true,
        }
      ),
      outputBlock(
        'dc_predicate_and',
        '%1 and %2',
        [
          blockValueInput(
            'LEFT',
            ['CandidatePredicate', 'Condition', 'Selector']
          ),
          blockValueInput(
            'RIGHT',
            ['CandidatePredicate', 'Condition', 'Selector']
          ),
        ],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_or',
        '%1 or %2',
        [
          blockValueInput(
            'LEFT',
            ['CandidatePredicate', 'Condition', 'Selector']
          ),
          blockValueInput(
            'RIGHT',
            ['CandidatePredicate', 'Condition', 'Selector']
          ),
        ],
        ['CandidatePredicate', 'Condition'],
        120
      ),
      outputBlock(
        'dc_predicate_not',
        'not %1',
        [
          blockValueInput(
            'PREDICATE',
            ['CandidatePredicate', 'Condition', 'Selector']
          ),
        ],
        ['CandidatePredicate', 'Condition'],
        120
      ),

      outputBlock(
        'dc_value_number',
        '%1',
        [
          {
            type: 'field_number',
            name: 'VALUE',
            value: 1,
            min: -10000,
            max: 10000,
            precision: 1,
          },
        ],
        ['Value', 'IntegerValue'],
        65
      ),
      outputBlock(
        'dc_value_boolean',
        '%1',
        [
          blockDropdown('VALUE', [
            ['true', 'true'],
            ['false', 'false'],
          ]),
        ],
        ['Value', 'Condition'],
        65
      ),
      outputBlock(
        'dc_value_candidate_attribute',
        'this item\'s %1',
        [blockDropdown('ATTRIBUTE', ATTRIBUTE_OPTIONS)],
        'Value',
        65
      ),
      outputBlock(
        'dc_value_aggregate',
        '%1 %3 for %2',
        [
          blockDropdown('MODE', [
            ['sum', 'sum'],
            ['minimum', 'min'],
            ['maximum', 'max'],
            ['distinct count', 'count_distinct'],
          ]),
          blockValueInput('SELECTOR', 'Selector'),
          blockValueInput('VALUE', 'Value'),
        ],
        ['Value', 'IntegerValue'],
        65
      ),
      outputBlock(
        'dc_value_count',
        'count %1',
        [blockValueInput('SELECTOR', 'Selector')],
        ['Value', 'IntegerValue'],
        65
      ),
      outputBlock(
        'dc_value_exists',
        'there is at least one %1',
        [blockValueInput('SELECTOR', 'Selector')],
        ['Value', 'Condition'],
        65
      ),
      outputBlock(
        'dc_value_attribute',
        '%1 %2',
        [
          blockDropdown(
            'ATTRIBUTE',
            SELECTOR_ATTRIBUTE_OPTIONS
          ),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        'Value',
        65
      ),
      outputBlock(
        'dc_value_base_stat',
        'base %1 of %2',
        [
          blockDropdown('ATTRIBUTE', [
            ['cost', 'cost'],
            ['ATK', 'attack'],
            ['HP', 'hp'],
          ]),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        ['Value', 'IntegerValue'],
        65
      ),
      outputBlock(
        'dc_value_buff',
        '%1 buff of %2',
        [
          blockDropdown('ATTRIBUTE', [
            ['cost', 'cost'],
            ['ATK', 'attack'],
            ['maximum HP', 'maxHp'],
          ]),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        ['Value', 'IntegerValue'],
        65
      ),
      outputBlock(
        'dc_value_status',
        '%1 counter of %2',
        [
          blockDropdown(
            'STATUS',
            STATUSES.map((value) => [value, value])
          ),
          blockValueInput('SELECTOR', 'Selector'),
        ],
        ['Value', 'IntegerValue'],
        65
      ),
      outputBlock(
        'dc_value_empty_slots',
        'empty slots in %1',
        [blockValueInput('SELECTOR', 'Selector')],
        ['Value', 'IntegerValue'],
        65
      ),
      outputBlock(
        'dc_value_player_soul',
        'SOUL of %1',
        [blockValueInput('PLAYER', 'Selector')],
        ['Value', 'EnumValue'],
        65
      ),
      outputBlock(
        'dc_value_unique_values',
        'unique values from %1 by %2',
        [
          blockValueInput('SELECTOR', 'Selector'),
          blockValueInput('VALUE', 'Value'),
        ],
        ['Iterable', 'ValueList'],
        65
      ),
      outputBlock(
        'dc_value_unique_tribes',
        'unique Tribes in %1',
        [blockValueInput('SELECTOR', 'Selector')],
        ['Iterable', 'TribeList'],
        65
      ),
      outputBlock(
        'dc_value_count_unique_tribes',
        'count unique Tribes in %1',
        [blockValueInput('SELECTOR', 'Selector')],
        ['Value', 'IntegerValue'],
        65
      ),
      outputBlock(
        'dc_value_math',
        '%1 %2 %3',
        [
          blockValueInput('LEFT', 'IntegerValue'),
          blockDropdown('OPERATOR', [
            ['+', 'add'],
            ['−', 'subtract'],
            ['×', 'multiply'],
            ['÷', 'divide'],
            ['//', 'floor_divide'],
            ['mod', 'modulo'],
          ]),
          blockValueInput('RIGHT', 'IntegerValue'),
        ],
        ['Value', 'IntegerValue'],
        45
      ),
      outputBlock(
        'dc_value_negate',
        'negative %1',
        [blockValueInput('VALUE', 'IntegerValue')],
        ['Value', 'IntegerValue'],
        45
      ),
      outputBlock(
        'dc_value_clamp',
        'clamp %1 between %2 and %3',
        [
          blockValueInput('VALUE', 'IntegerValue'),
          blockValueInput('LOWER', 'IntegerValue'),
          blockValueInput('UPPER', 'IntegerValue'),
        ],
        ['Value', 'IntegerValue'],
        45
      ),
      outputBlock(
        'dc_value_least_greatest',
        '%1 of %2 and %3',
        [
          blockDropdown('MODE', [
            ['smaller', 'least'],
            ['larger', 'greatest'],
          ]),
          blockValueInput('LEFT', 'IntegerValue'),
          blockValueInput('RIGHT', 'IntegerValue'),
        ],
        ['Value', 'IntegerValue'],
        45
      ),

      {
        type: 'dc_effect_noop',
        message0: 'Do nothing',
        previousStatement: 'Effect',
        nextStatement: 'Effect',
        colour: 290,
      },
      {
        type: 'dc_effect_program',
        message0: 'Program (%1)',
        args0: [
          blockValueInput('AMOUNT', 'IntegerValue'),
        ],
        message1: 'to do %1',
        args1: [
          blockStatementInput('EFFECT'),
        ],
        previousStatement: 'Effect',
        nextStatement: 'Effect',
        colour: 290,
      },
      {
        type: 'dc_effect_switch',
        message0: 'Switch: left: %1',
        args0: [
          blockStatementInput('LEFT'),
        ],
        message1: 'right: %1',
        args1: [
          blockStatementInput('RIGHT'),
        ],
        previousStatement: 'Effect',
        nextStatement: 'Effect',
        colour: 290,
      },
      {
        type: 'dc_effect_then',
        message0: 'Do %1',
        args0: [
          blockStatementInput('EFFECT'),
        ],
        message1: 'to do %1',
        args1: [
          blockStatementInput('THEN'),
        ],
        message2: 'otherwise %1',
        args2: [
          blockStatementInput('ELSE'),
        ],
        previousStatement: 'Effect',
        nextStatement: 'Effect',
        colour: 20,
      },
      {
        type: 'dc_effect_if',
        message0: 'If %1',
        args0: [
          blockValueInput(
            'CONDITION',
            ['Condition', 'Selector']
          ),
        ],
        message1: 'then %1',
        args1: [
          blockStatementInput('THEN'),
        ],
        message2: 'else %1',
        args2: [
          blockStatementInput('ELSE'),
        ],
        previousStatement: 'Effect',
        nextStatement: 'Effect',
        colour: 20,
      },
      {
        type: 'dc_effect_for',
        message0: 'Repeat %1 times',
        args0: [
          {
            type: 'field_number',
            name: 'COUNT',
            value: 1,
            min: 0,
            max: 128,
            precision: 1,
          },
        ],
        message1: 'index variable %1 do %2',
        args1: [
          blockText('INDEX_VARIABLE'),
          blockStatementInput('EFFECT'),
        ],
        previousStatement: 'Effect',
        nextStatement: 'Effect',
        colour: 20,
      },
      {
        type: 'dc_effect_for_each',
        message0: 'For each %1 as variable %2',
        args0: [
          blockValueInput(
            'ITERABLE',
            ['Selector', 'ValueList', 'IntegerList', 'TribeList']
          ),
          blockText('VARIABLE', 'item'),
        ],
        message1: 'index variable %1',
        args1: [
          blockText('INDEX_VARIABLE'),
        ],
        message2: 'do %1',
        args2: [
          blockStatementInput('EFFECT'),
        ],
        previousStatement: 'Effect',
        nextStatement: 'Effect',
        colour: 20,
      },

      ...Object.entries(ACTION_SPECS)
        .filter(([, spec]) => !spec.customBlock)
        .map(([type, spec]) => actionBlockJson(type, spec)),
    ]);

    Blockly.Blocks.dc_ability = {
      init() {
        this.appendDummyInput()
          .appendField(new Blockly.FieldDropdown(() => (
            dropdownOptionsForRestore(
              this,
              'ABILITY',
              abilityOptions(this)
            )
          )), 'ABILITY')
          .appendField(':');

        this.setNextStatement(true, 'Effect');
        this.setColour(290);
      },
    };

    Blockly.Blocks.dc_variable_reference = {
      init() {
        this.appendDummyInput()
          .appendField('variable')
          .appendField(new Blockly.FieldDropdown(() => (
            variableOptions(this)
          )), 'VARIABLE');

        this.setOutput(true, 'Value');
        this.setColour(330);

        installDynamicOutputChecks(this, {
          fields: ['VARIABLE'],
          resolve: (fieldValue) => {
          const variableType = visibleVariables(this).get(
              fieldValue('VARIABLE')
          );

            return variableOutputChecks(variableType);
          },
        });
      },
    };

    Blockly.Blocks.dc_action_set_variable = {
      init() {
        this.appendValueInput('VALUE')
          .setCheck([
            'Selector',
            'Value',
            'Condition',
          ])
          .appendField('Set variable')
          .appendField(new Blockly.FieldDropdown(() => (
            variableOptions(this)
          )), 'VARIABLE')
          .appendField('to');

        this.setPreviousStatement(true, 'Effect');
        this.setNextStatement(true, 'Effect');
        this.setColour(330);
      },
    };

    Blockly.Blocks.dc_effect_store_result = {
      init() {
        this.appendStatementInput('ACTION')
          .setCheck('Effect')
          .appendField('Run action');
        this.appendDummyInput()
          .appendField('and save its result as')
          .appendField(new Blockly.FieldDropdown(() => (
            variableOptions(this, 'result')
          )), 'VARIABLE');

        this.setPreviousStatement(true, 'Effect');
        this.setNextStatement(true, 'Effect');
        this.setColour(330);
      },
    };

    Blockly.Blocks.dc_action_release_caught_card = {
      init() {
        this.appendValueInput('CATCHER')
          .setCheck('Selector')
          .appendField('Release caught card from');
        this.appendDummyInput()
          .appendField('into variable')
          .appendField(new Blockly.FieldDropdown(() => (
            variableOptions(this, 'selector')
          )), 'VARIABLE');

        this.setPreviousStatement(true, 'Effect');
        this.setNextStatement(true, 'Effect');
        this.setInputsInline(true);
        this.setColour(20);
      },
    };

    Blockly.Blocks.dc_value_enum = {
      init() {
        this.appendDummyInput()
          .appendField('enum')
          .appendField(new Blockly.FieldDropdown(() => (
            dropdownOptionsForRestore(
              this,
              'ENUM',
              Object.keys(ENUM_VALUES).map((name) => [
                name.replaceAll(/([A-Z])/g, ' $1'),
                name,
              ])
            )
          )), 'ENUM')
          .appendField(new Blockly.FieldDropdown(() => (
            dropdownOptionsForRestore(
              this,
              'MEMBER',
              ENUM_VALUES[this.getFieldValue('ENUM')]
              || [['not available', '']]
            )
          )), 'MEMBER');

        this.setOutput(true, ['Value', 'EnumValue']);
        this.setColour(65);

        installDynamicOutputChecks(this, {
          fields: ['ENUM'],
          resolve: (fieldValue) => (
            enumOutputChecks(fieldValue('ENUM'))
          ),
        });
      },
    };

    for (const type of [
      'dc_selector_event_entity',
      'dc_selector_event_snapshot',
    ]) {
      Blockly.Blocks[type] = {
        init() {
          const detailKind = (
            type === 'dc_selector_event_entity'
              ? 'live'
              : 'snapshots'
          );

          this.appendDummyInput()
            .appendField(
              detailKind === 'live'
                ? 'current event'
                : ''
            )
            .appendField(new Blockly.FieldDropdown(() => (
              dropdownOptionsForRestore(
                this,
                'ROLE',
                eventDetailOptions(this, detailKind)
              )
            )), 'ROLE')
            .appendField(
              detailKind === 'live'
                ? ''
                : 'when this event happened'
            );

          this.setOutput(true, 'Selector');
          this.setColour(260);
        },
      };
    }

    Blockly.Blocks.dc_value_event = {
      init() {
        this.appendDummyInput()
          .appendField('this event\'s')
          .appendField(new Blockly.FieldDropdown(() => (
            dropdownOptionsForRestore(
              this,
              'FIELD',
              eventDetailOptions(this, 'values')
            )
          )), 'FIELD');

        this.setOutput(true, 'Value');
        this.setColour(260);

        installDynamicOutputChecks(this, {
          fields: ['FIELD'],
          resolve: (fieldValue) => (
            eventValueOutputChecks(fieldValue('FIELD'))
          ),
        });
      },
    };

    const uniqueValuesInit = Blockly.Blocks.dc_value_unique_values.init;
    Blockly.Blocks.dc_value_unique_values.init = function () {
      uniqueValuesInit.call(this);

      installDynamicOutputChecks(this, {
        resolve: () => {
          const checks = (
            this.getInputTargetBlock('VALUE')
              ?.outputConnection
              ?.getCheck()
            || []
          );

          if (checks.includes('IntegerValue')) {
            return [
              'Iterable',
              'IntegerList',
            ];
          }

          if (checks.includes('TribeValue')) {
            return [
              'Iterable',
              'TribeList',
            ];
          }

          return [
            'Iterable',
            'ValueList',
          ];
        },
      });
    };

    function installAttributeOutputChecks(type) {
      const definition = Blockly.Blocks[type];
      const init = definition.init;

      definition.init = function () {
        init.call(this);

        installDynamicOutputChecks(this, {
          fields: ['ATTRIBUTE'],
          resolve: (fieldValue) => (
            attributeOutputChecks(fieldValue('ATTRIBUTE'))
          ),
        });
      };
    }

    installAttributeOutputChecks('dc_value_candidate_attribute');
    installAttributeOutputChecks('dc_value_attribute');
  }

  function blocklyToolbox(kind) {
    const block = (type, options = {}) => ({
      kind: 'block',
      type,
      ...options,
    });

    const shadow = (type, options = {}) => ({
      shadow: {
        type,
        ...options,
      },
    });

    const category = (name, colour, contents) => ({
      kind: 'category',
      name,
      colour,
      contents,
    });

    const label = (text) => ({kind: 'label', text});
    const separator = () => ({kind: 'sep', gap: 32});
    const blocks = (types) => types.map((type) => block(type));

    const numberShadow = (value) => (
      shadow('dc_value_number', {
        fields: {
          VALUE: value,
        },
      })
    );

    const randomSelectorShadow = (selectorType) => (
      shadow('dc_selector_random', {
        inputs: {
          COUNT: numberShadow(1),
          SELECTOR: shadow(selectorType),
        },
      })
    );

    const generatedCardShadow = () => (
      shadow('dc_selector_generate', {
        inputs: {
          COUNT: numberShadow(1),
          SELECTOR: shadow('dc_selector_named'),
          CONTROLLER: shadow('dc_selector_you'),
        },
      })
    );

    return {
      kind: 'categoryToolbox',
      contents: [
        category(
          'Build abilities & logic',
          290,
          [
            category(
              'Abilities',
              290,
              [
                label('Named abilities'),
                ...ROOT_CONFIG[kind].abilities.map(
                  (ability) => ({
                    kind: 'block',
                    type: 'dc_ability',
                    fields: {
                      ABILITY: ability,
                    },
                  })
                ),
                separator(),
                label('Reusable effects'),
                block('dc_effect_program', {
                  inputs: {
                    AMOUNT: numberShadow(1),
                  },
                }),
                block('dc_effect_switch'),
                block('dc_effect_noop'),
              ]
            ),
            category(
              'After an event',
              290,
              [
                block('dc_reaction'),
              ]
            ),
            category(
              'Event details',
              260,
              blocks([
                'dc_selector_event_entity',
                'dc_selector_event_snapshot',
                'dc_value_event',
              ])
            ),
            category(
              'Logic & repetition',
              20,
              blocks([
                'dc_effect_then',
                'dc_effect_if',
                'dc_effect_for',
                'dc_effect_for_each',
              ])
            ),
            category(
              'Variables & choices',
              330,
              [
                label('Variables'),
                ...blocks([
                  'dc_variable_declaration',
                  'dc_variable_reference',
                  'dc_action_set_variable',
                  'dc_effect_store_result',
                ]),
                separator(),
                label('Choices'),
                block('dc_action_choose', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                    OPTIONS: shadow('dc_selector_deck'),
                  },
                }),
                block('dc_selector_choice_selected'),
                block('dc_selector_choice_not_selected'),
              ]
            ),
          ]
        ),
        category(
          'Change the game',
          20,
          [
            category(
              'Damage & healing',
              20,
              [
                block('dc_action_hit', {
                  inputs: {
                    DAMAGE: numberShadow(1),
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_heal', {
                  inputs: {
                    AMOUNT: numberShadow(1),
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_kill', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_attack', {
                  inputs: {
                    ATTACKER: shadow('dc_selector_self'),
                    DEFENDER: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_refresh_attacks', {
                  inputs: {
                    TARGET: shadow('dc_selector_self'),
                  },
                }),
              ]
            ),
            category(
              'Card stats, keywords & statuses',
              20,
              [
                label('Stats'),
                block('dc_action_buff', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                    COST: numberShadow(0),
                    ATTACK: numberShadow(1),
                    HP: numberShadow(1),
                  },
                }),
                block('dc_action_set_stats', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                    COST: numberShadow(0),
                    ATTACK: numberShadow(1),
                    HP: numberShadow(1),
                  },
                }),
                block('dc_action_set_base_stats', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                    COST: numberShadow(0),
                    ATTACK: numberShadow(1),
                    HP: numberShadow(1),
                  },
                }),
                block('dc_action_swap_stats', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_halve_stats', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                separator(),
                label('Keywords'),
                block('dc_action_add_keyword', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_remove_keyword', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                separator(),
                label('Statuses'),
                block('dc_action_set_status', {
                  fields: {
                    STATUS: 'DODGE',
                  },
                  inputs: {
                    VALUE: numberShadow(1),
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_remove_status', {
                  fields: {
                    STATUS: 'DODGE',
                  },
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_silence', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_paralyze', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_remove_negative_effects', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
              ]
            ),
            category(
              'Draw, move & create cards',
              20,
              [
                label('Draw and reveal'),
                block('dc_action_reveal', {
                  inputs: {
                    CARD: shadow('dc_selector_hand'),
                  },
                }),
                block('dc_action_draw', {
                  inputs: {
                    CARD: shadow('dc_selector_target'),
                    PLAYER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_action_draw_next', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_action_draw_up_to', {
                  inputs: {
                    COUNT: numberShadow(1),
                  },
                }),
                block('dc_action_take_fatigue_damage', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                  },
                }),
                separator(),
                label('Move and remove'),
                block('dc_action_move', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                    CONTROLLER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_action_swap_cards', {
                  inputs: {
                    CARD1: shadow('dc_selector_self'),
                    CARD2: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_erase', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                separator(),
                label('Create and transform'),
                block('dc_action_summon', {
                  inputs: {
                    CARD: generatedCardShadow(),
                    CONTROLLER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_action_cast', {
                  inputs: {
                    CARD: generatedCardShadow(),
                    CONTROLLER: shadow('dc_selector_you'),
                    TARGET: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_cast_random', {
                  inputs: {
                    CARD: generatedCardShadow(),
                    CONTROLLER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_action_fill_board', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                    CARD: generatedCardShadow(),
                  },
                }),
                block('dc_action_fill_hand', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                    CARD: generatedCardShadow(),
                  },
                }),
                block('dc_action_transform_card', {
                  inputs: {
                    TARGET: shadow('dc_selector_target'),
                    NEW_CARD: generatedCardShadow(),
                  },
                }),
                block('dc_action_catch', {
                  inputs: {
                    CATCHER: shadow('dc_selector_self'),
                    CARD: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_release_caught_card', {
                  inputs: {
                    CATCHER: shadow('dc_selector_self'),
                  },
                }),
              ]
            ),
            category(
              'Change players',
              20,
              [
                block('dc_action_set_player_hp', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                    HP: numberShadow(1),
                  },
                }),
                block('dc_action_earn_gold', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                    AMOUNT: numberShadow(1),
                  },
                }),
                block('dc_action_spend_gold', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                    AMOUNT: numberShadow(1),
                  },
                }),
                block('dc_action_set_gold', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                    AMOUNT: numberShadow(1),
                  },
                }),
                block('dc_action_skip_next_turn', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                  },
                }),
              ]
            ),
            category(
              'Trigger / toggle abilities & Delay',
              20,
              [
                label('Abilities'),
                block('dc_action_trigger_ability', {
                  inputs: {
                    TARGET: shadow('dc_selector_self'),
                  },
                }),
                block('dc_action_toggle_ability', {
                  inputs: {
                    TARGET: shadow('dc_selector_self'),
                  },
                }),
                separator(),
                label('Delay'),
                block('dc_action_schedule_delay', {
                  inputs: {
                    TARGET: shadow('dc_selector_self'),
                  },
                }),
              ]
            ),
            category(
              'Artifacts & enchantments',
              20,
              [
                label('Artifacts'),
                block('dc_action_add_artifact', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_action_toggle_artifact', {
                  inputs: {
                    ARTIFACT: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_transform_artifact', {
                  inputs: {
                    ARTIFACT: shadow('dc_selector_target'),
                  },
                }),
                block('dc_action_update_artifact_counter', {
                  inputs: {
                    ARTIFACT: shadow('dc_selector_target'),
                    DELTA: numberShadow(1),
                  },
                }),
                separator(),
                label('Enchantments'),
                block('dc_action_enchant', {
                  inputs: {
                    SLOT: randomSelectorShadow(
                      'dc_selector_all_enchantments'
                    ),
                  },
                }),
                block('dc_action_remove_enchantment', {
                  inputs: {
                    TARGET: shadow('dc_selector_all_enchantments'),
                  },
                }),
                block('dc_action_transform_enchantment', {
                  inputs: {
                    TARGET: shadow('dc_selector_all_enchantments'),
                  },
                }),
                block('dc_action_update_enchantment_counter', {
                  inputs: {
                    ENCHANTMENT: shadow('dc_selector_all_enchantments'),
                    DELTA: numberShadow(1),
                  },
                }),
              ]
            ),
          ]
        ),
        category(
          'Choose things to affect',
          210,
          [
            category(
              'This effect',
              210,
              blocks([
                'dc_selector_self',
                'dc_selector_target',
                'dc_selector_killer',
                'dc_selector_attacker',
                'dc_selector_defender',
                'dc_selector_loop_copy',
                'dc_selector_trigger_card',
                'dc_selector_death_slot',
              ])
            ),
            category(
              'Players & monsters',
              210,
              [
                ...blocks([
                  'dc_selector_you',
                  'dc_selector_opponent',
                  'dc_selector_turn_player',
                  'dc_selector_all_players',
                  'dc_selector_ally_monsters',
                  'dc_selector_enemy_monsters',
                  'dc_selector_all_monsters',
                  'dc_selector_allies',
                  'dc_selector_enemies',
                ]),
                block('dc_selector_controller_of', {
                  inputs: {
                    SELECTOR: shadow('dc_selector_self'),
                  },
                }),
                block('dc_selector_opponent_of', {
                  inputs: {
                    SELECTOR: shadow('dc_selector_self'),
                  },
                }),
              ]
            ),
            category(
              'Cards, artifacts & enchantments',
              210,
              [
                block('dc_selector_zone', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_selector_card_library'),
                block('dc_selector_named'),
                block('dc_selector_artifact_of_player', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                  },
                }),
              ]
            ),
            category(
              'Board & hand',
              210,
              [
                ...blocks([
                  'dc_selector_ally_slots',
                  'dc_selector_enemy_slots',
                  'dc_selector_all_slots',
                  'dc_selector_this_slot_monster',
                  'dc_selector_all_enchantments',
                ]),
                block('dc_selector_board_slots_of', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_selector_enchantments_of', {
                  inputs: {
                    PLAYER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_selector_relative_board', {
                  inputs: {
                    SELECTOR: shadow('dc_selector_self'),
                  },
                }),
                block('dc_selector_relative_hand', {
                  inputs: {
                    SELECTOR: shadow('dc_selector_self'),
                  },
                }),
                block('dc_selector_slot_of', {
                  inputs: {
                    SELECTOR: shadow('dc_selector_self'),
                  },
                }),
                block('dc_selector_slot_content', {
                  inputs: {
                    SELECTOR: shadow('dc_selector_ally_slots'),
                  },
                }),
              ]
            ),
            category(
              'Selection & ordering',
              180,
              [
                block('dc_selector_filter', {
                  inputs: {
                    SELECTOR: shadow('dc_selector_ally_monsters'),
                    PREDICATE: shadow('dc_predicate_damaged'),
                  },
                }),
                block('dc_selector_combine'),
                block('dc_selector_index', {
                  inputs: {
                    INDEX: numberShadow(1),
                    SELECTOR: shadow('dc_selector_hand'),
                  },
                }),
                block('dc_selector_take', {
                  inputs: {
                    COUNT: numberShadow(1),
                    SELECTOR: shadow('dc_selector_hand'),
                  },
                }),
                block('dc_selector_random', {
                  inputs: {
                    COUNT: numberShadow(1),
                    SELECTOR: shadow('dc_selector_enemy_monsters'),
                  },
                }),
                ...blocks([
                  'dc_selector_minmax',
                  'dc_selector_left_rightmost',
                  'dc_selector_sort',
                  'dc_selector_distinct',
                  'dc_selector_limit_per',
                ]),
              ]
            ),
            category(
              'Generate & copy Cards',
              180,
              [
                block('dc_selector_generate', {
                  inputs: {
                    COUNT: numberShadow(1),
                    SELECTOR: randomSelectorShadow(
                      'dc_selector_card_library'
                    ),
                    CONTROLLER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_selector_discover', {
                  inputs: {
                    COUNT: numberShadow(1),
                    CONTROLLER: shadow('dc_selector_you'),
                  },
                }),
                block('dc_selector_copy'),
                block('dc_selector_next_lost_soul'),
              ]
            ),
          ]
        ),
        category(
          'Conditions & values',
          120,
          [
            category(
              'Filters',
              120,
              blocks([
                'dc_predicate_card_type',
                'dc_predicate_damaged',
                'dc_predicate_dead',
                'dc_predicate_has_negative_effects',
                'dc_predicate_has_ability',
                'dc_predicate_has_keyword',
                'dc_predicate_has_status',
                'dc_predicate_has_tribe',
                'dc_predicate_has_any_tribe',
                'dc_predicate_expansion',
                'dc_predicate_rarity',
                'dc_predicate_generated',
                'dc_predicate_generated_by',
                'dc_predicate_slot_state',
                'dc_predicate_slot_has_enchantment',
                'dc_predicate_has_artifact',
                'dc_predicate_attribute_compare',
                'dc_predicate_compare',
                'dc_predicate_and',
                'dc_predicate_or',
                'dc_predicate_not',
              ])
            ),
            category(
              'Properties & values',
              65,
              blocks([
                'dc_value_number',
                'dc_value_boolean',
                'dc_value_enum',
                'dc_value_candidate_attribute',
                'dc_value_attribute',
                'dc_value_base_stat',
                'dc_value_buff',
                'dc_value_status',
                'dc_value_empty_slots',
                'dc_value_synergy_triggered',
                'dc_value_player_soul',
              ])
            ),
            category(
              'Counts & totals',
              65,
              blocks([
                'dc_value_count',
                'dc_value_exists',
                'dc_value_aggregate',
                'dc_value_unique_values',
                'dc_value_unique_tribes',
                'dc_value_count_unique_tribes',
              ])
            ),
            category(
              'Math',
              45,
              blocks([
                'dc_value_math',
                'dc_value_negate',
                'dc_value_clamp',
                'dc_value_least_greatest',
              ])
            ),
          ]
        ),
        {
          kind: 'search',
          name: 'Search',
          contents: [],
        },
      ],
    };
  }

  function requiredDefinitionName(block, fieldName, kind) {
    const name = block.getFieldValue(fieldName).trim();

    if (name.length === 0) {
      const error = new Error(
        `A ${kind} display name is required.`
      );
      error.blockId = block.id;
      throw error;
    }

    return name;
  }

  function requiredInput(block, name) {
    const child = block.getInputTargetBlock(name);

    if (child === null) {
      const error = new Error(
        `Block ${block.type} requires input ${name}.`
      );
      error.blockId = block.id;
      throw error;
    }

    return child;
  }

  function nodeFromBlock(block, value) {
    return {
      nodeId: block.id,
      ...value,
    };
  }

  function compileActionFromSpec(block) {
    const spec = ACTION_SPECS[block.type];
    if (spec === undefined) {
      return null;
    }

    const result = {
      node: spec.node,
      ...spec.fixed,
    };

    for (const argument of spec.args) {
      if (argument.type === 'input') {
        const child = block.getInputTargetBlock(argument.name);

        if (child === null) {
          if (argument.optional) {
            continue;
          }

          requiredInput(block, argument.name);
        }

        const value = compileExpression(child);

        if (argument.transform === 'position') {
          result[argument.argument] = {
            nodeId: block.id,
            node: 'value.attribute',
            selector: value,
            attribute: 'position',
          };
        } else {
          result[argument.argument] = value;
        }

        continue;
      }

      if (argument.type === 'dropdown') {
        result[argument.argument] = block.getFieldValue(
          argument.name
        );
        continue;
      }

      if (argument.type === 'boolean') {
        result[argument.argument] = {
          nodeId: block.id,
          node: 'value.literal',
          value: block.getFieldValue(argument.name) === 'true',
        };
        continue;
      }

      if (argument.type === 'definition') {
        result[argument.argument] = {
          nodeId: block.id,
          node: `selector.${argument.kind}_by_name`,
          name: requiredDefinitionName(
            block,
            argument.name,
            argument.kind
          ),
        };
        continue;
      }

      if (argument.type === 'variable') {
        result[argument.argument] = block
          .getFieldValue(argument.name)
          .trim();
      }
    }

    return nodeFromBlock(block, result);
  }

  function compileExpression(block) {
    const simple = SIMPLE_EXPRESSIONS[block.type];
    if (simple !== undefined) {
      return nodeFromBlock(block, {
        node: simple.node,
      });
    }

    if (block.type === 'dc_variable_reference') {
      return nodeFromBlock(block, {
        node: 'variable.reference',
        variable: block.getFieldValue('VARIABLE').trim(),
      });
    }

    if (block.type === 'dc_predicate_has_artifact') {
      return nodeFromBlock(block, {
        node: 'selector.filter',
        selector: compileExpression(
          requiredInput(block, 'PLAYER')
        ),
        predicate: {
          nodeId: block.id,
          node: 'predicate.has_artifact',
          name: requiredDefinitionName(
            block,
            'NAME',
            'artifact'
          ),
        },
      });
    }

    const spec = EXPRESSION_SPECS[block.type];
    if (spec === undefined) {
      const error = new Error(
        `Unsupported expression block ${block.type}.`
      );
      error.blockId = block.id;
      throw error;
    }

    const result = {
      node: (
        typeof spec.node === 'function'
          ? spec.node(block)
          : spec.node
      ),
    };

    for (
      const [argument, inputName]
      of Object.entries(spec.inputs || {})
    ) {
      result[argument] = compileExpression(
        requiredInput(block, inputName)
      );
    }

    for (
      const [argument, inputName]
      of Object.entries(spec.nullableInputs || {})
    ) {
      const child = block.getInputTargetBlock(inputName);
      result[argument] = (
        child === null
          ? null
          : compileExpression(child)
      );
    }

    for (
      const [argument, fieldSpec]
      of Object.entries(spec.fields || {})
    ) {
      const fieldName = Array.isArray(fieldSpec)
        ? fieldSpec[0]
        : fieldSpec;
      const transform = Array.isArray(fieldSpec)
        ? fieldSpec[1]
        : null;
      const value = block.getFieldValue(fieldName);

      result[argument] = (
        transform === null
          ? value
          : transform(value)
      );
    }

    for (
      const [argument, inputNames]
      of Object.entries(spec.inputLists || {})
    ) {
      result[argument] = inputNames.map(
        (inputName) => compileExpression(
          requiredInput(block, inputName)
        )
      );
    }

    return nodeFromBlock(block, result);
  }

  function compileEffectBlock(block) {
    const action = compileActionFromSpec(block);
    if (action !== null) {
      return action;
    }

    switch (block.type) {
      case 'dc_effect_noop':
        return nodeFromBlock(block, {
          node: 'effect.noop',
        });

      case 'dc_effect_program':
        return nodeFromBlock(block, {
          node: 'effect.program',
          amount: compileExpression(
            requiredInput(block, 'AMOUNT')
          ),
          effect: compileEffectSequence(
            requiredInput(block, 'EFFECT')
          ),
        });

      case 'dc_effect_switch':
        return nodeFromBlock(block, {
          node: 'effect.switch',
          left: compileEffectSequence(
            requiredInput(block, 'LEFT')
          ),
          right: compileEffectSequence(
            requiredInput(block, 'RIGHT')
          ),
        });

      case 'dc_effect_then': {
        const elseBlock = block.getInputTargetBlock('ELSE');

        return nodeFromBlock(block, {
          node: 'effect.then',
          effect: compileEffectSequence(
            requiredInput(block, 'EFFECT')
          ),
          then: compileEffectSequence(
            requiredInput(block, 'THEN')
          ),
          else: (
            elseBlock === null
              ? null
              : compileEffectSequence(elseBlock)
          ),
        });
      }

      case 'dc_effect_store_result': {
        const actionBlock = requiredInput(block, 'ACTION');

        if (
          ACTION_SPECS[actionBlock.type] === undefined
          || actionBlock.getNextBlock() !== null
        ) {
          const error = new Error(
            'Store result requires exactly one Action block.'
          );
          error.blockId = block.id;
          throw error;
        }

        return nodeFromBlock(block, {
          node: 'effect.store_result',
          variable: block.getFieldValue('VARIABLE'),
          action: compileEffectBlock(actionBlock),
        });
      }

      case 'dc_effect_for': {
        const indexVariable = block
          .getFieldValue('INDEX_VARIABLE')
          .trim();

        return nodeFromBlock(block, {
          node: 'effect.for',
          count: {
            nodeId: block.id,
            node: 'value.literal',
            value: Number(block.getFieldValue('COUNT')),
          },
          indexVariable: indexVariable || null,
          effect: compileEffectSequence(
            requiredInput(block, 'EFFECT')
          ),
        });
      }

      case 'dc_effect_for_each': {
        const indexVariable = block
          .getFieldValue('INDEX_VARIABLE')
          .trim();

        return nodeFromBlock(block, {
          node: 'effect.for_each',
          iterable: compileExpression(
            requiredInput(block, 'ITERABLE')
          ),
          variable: block
            .getFieldValue('VARIABLE')
            .trim(),
          indexVariable: indexVariable || null,
          effect: compileEffectSequence(
            requiredInput(block, 'EFFECT')
          ),
        });
      }

      case 'dc_action_set_variable':
        return nodeFromBlock(block, {
          node: 'action.set_variable',
          variable: block
            .getFieldValue('VARIABLE')
            .trim(),
          value: compileExpression(
            requiredInput(block, 'VALUE')
          ),
        });

      case 'dc_effect_if': {
        const elseBlock = block.getInputTargetBlock('ELSE');

        return nodeFromBlock(block, {
          node: 'effect.if',
          condition: compileExpression(
            requiredInput(block, 'CONDITION')
          ),
          then: compileEffectSequence(
            requiredInput(block, 'THEN')
          ),
          else: (
            elseBlock === null
              ? null
              : compileEffectSequence(elseBlock)
          ),
        });
      }

      default: {
        const error = new Error(
          `Unsupported effect block ${block.type}.`
        );
        error.blockId = block.id;
        throw error;
      }
    }
  }

  function compileEffectSequence(firstBlock) {
    const effects = [];
    let current = firstBlock;

    while (current !== null) {
      effects.push(compileEffectBlock(current));
      current = current.getNextBlock();
    }

    if (effects.length === 1) {
      return effects[0];
    }

    return {
      nodeId: firstBlock.id,
      node: 'effect.sequence',
      effects,
    };
  }

  function workspaceProgram(workspace, kind) {
    const config = ROOT_CONFIG[kind];

    if (!config) {
      throw new Error(
        `Unsupported entity kind ${JSON.stringify(kind)}.`
      );
    }

    const topBlocks = workspace.getTopBlocks(false);
    const roots = topBlocks.filter(
      (block) => block.type === config.block
    );

    if (roots.length !== 1) {
      throw new Error(
        'The workspace must contain exactly one implementation root.'
      );
    }

    const root = roots[0];
    const abilities = [];
    const variables = [];
    const reactions = [];
    const seenAbilities = new Set();
    const seenVariables = new Set();

    for (const block of topBlocks) {
      if (block.type !== 'dc_variable_declaration') continue;

      const name = block.getFieldValue('NAME').trim();
      if (!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(name)) {
        const error = new Error(
          `Invalid variable name ${JSON.stringify(name)}.`
        );
        error.blockId = block.id;
        throw error;
      }

      if (seenVariables.has(name)) {
        const error = new Error(
          `Variable ${JSON.stringify(name)} is declared more than once.`
        );
        error.blockId = block.id;
        throw error;
      }

      seenVariables.add(name);
      variables.push({
        nodeId: block.id,
        name,
        type: block.getFieldValue('TYPE'),
      });
    }

    for (const block of topBlocks) {
      if (
        block === root
        || block.type === 'dc_variable_declaration'
      ) {
        continue;
      }

      if (block.type === 'dc_reaction') {
        const effect = block.getNextBlock();
        if (effect === null) {
          const error = new Error(
            'An event reaction requires at least one effect.'
          );
          error.blockId = block.id;
          throw error;
        }

        const condition = block.getInputTargetBlock(
          'CONDITION'
        );

        reactions.push({
          nodeId: block.id,
          event: block.getFieldValue('EVENT'),
          condition: (
            condition === null
              ? null
              : compileExpression(condition)
          ),
          effect: compileEffectSequence(effect),
        });
        continue;
      }

      if (block.type !== 'dc_ability') {
        const error = new Error(
          `Disconnected block ${block.type} is not allowed.`
        );
        error.blockId = block.id;
        throw error;
      }

      const ability = block.getFieldValue('ABILITY');
      const effect = block.getNextBlock();

      if (!config.abilities.includes(ability)) {
        const error = new Error(
          `${ABILITY_LABELS[ability] || ability} ability is not available to ${kind} entities.`
        );
        error.blockId = block.id;
        throw error;
      }

      if (seenAbilities.has(ability)) {
        const error = new Error(
          `${ABILITY_LABELS[ability] || ability} ability is declared more than once.`
        );
        error.blockId = block.id;
        throw error;
      }

      if (effect === null) {
        const error = new Error(
          `${ABILITY_LABELS[ability] || ability} ability requires at least one effect.`
        );
        error.blockId = block.id;
        throw error;
      }

      seenAbilities.add(ability);
      abilities.push({
        nodeId: block.id,
        ability,
        effect: compileEffectSequence(effect),
      });
    }

    const targetsBlock = (
      config.targets
        ? root.getInputTargetBlock('TARGETS')
        : null
    );
    const needBlock = (
      config.need
        ? root.getInputTargetBlock('NEED')
        : null
    );

    return {
      irVersion: 1,
      variables,
      targets: (
        targetsBlock === null
          ? null
          : compileExpression(targetsBlock)
      ),
      need: (
        needBlock === null
          ? null
          : compileExpression(needBlock)
      ),
      abilities,
      reactions,
    };
  }

  function createRootBlock(workspace, kind) {
    const block = workspace.newBlock(
      ROOT_CONFIG[kind].block
    );

    block.initSvg();
    block.render();
    block.moveBy(20, 20);
    return block;
  }

  function create(options) {
    if (
      !options
      || typeof options.httpUrl !== 'function'
    ) {
      throw new TypeError(
        'The content editor requires an httpUrl callback.'
      );
    }

    const databasePromise = openDatabase();
    const objectUrls = new Map();

    const state = {
      overlay: null,
      body: null,
      tab: 'collection',
      selectedId: null,
      importPreview: null,
      validation: null,
      workspace: null,
      workspaceEntityId: null,
      workspaceChanged: false,
    };

    function clearCatalogPreview() {
      localStorage.removeItem(
        CATALOG_PREVIEW_STORAGE_KEY
      );
    }

    function contentChanged() {
      state.validation = null;
      clearCatalogPreview();
    }

    function storeCatalogPreview(result, packId) {
      const preview = result.catalogPreview;

      if (
        !preview
        || typeof preview !== 'object'
      ) {
        clearCatalogPreview();
        throw new Error(
          'The validation server did not return a catalog preview.'
        );
      }

      const serverOrigin = new URL(options.httpUrl('/')).origin;

      localStorage.setItem(
        CATALOG_PREVIEW_STORAGE_KEY,
        JSON.stringify({
          previewVersion: 1,
          serverOrigin,
          packId,
          ...preview,
        })
      );
    }

    async function allEntities() {
      const database = await databasePromise;
      const transaction = database.transaction(
        'entities',
        'readonly'
      );
      const request = transaction
        .objectStore('entities')
        .getAll();

      const result = await requestValue(request);
      await transactionComplete(transaction);

      return result.sort((left, right) => (
        left.definition.name.localeCompare(
          right.definition.name
        )
      ));
    }

    async function allAssets() {
      const database = await databasePromise;
      const transaction = database.transaction(
        'assets',
        'readonly'
      );
      const request = transaction
        .objectStore('assets')
        .getAll();

      const result = await requestValue(request);
      await transactionComplete(transaction);

      return result;
    }

    async function backupAssets() {
      const assets = await allAssets();

      return Promise.all(
        assets.map(async (asset) => ({
          assetId: asset.assetId,
          mimeType: (
            asset.mimeType
            || asset.blob.type
          ),
          data: await blobToBase64(
            asset.blob
          ),
        }))
      );
    }

    async function entityById(contentId) {
      const database = await databasePromise;
      const transaction = database.transaction(
        'entities',
        'readonly'
      );
      const result = await requestValue(
        transaction.objectStore('entities').get(
          contentId
        )
      );

      await transactionComplete(transaction);
      return result;
    }

    async function putEntity(record) {
      const database = await databasePromise;
      const transaction = database.transaction(
        'entities',
        'readwrite'
      );

      transaction.objectStore('entities').put(record);
      await transactionComplete(transaction);
    }

    async function setting(key, fallback = null) {
      const database = await databasePromise;
      const transaction = database.transaction(
        'settings',
        'readonly'
      );
      const result = await requestValue(
        transaction.objectStore('settings').get(key)
      );

      await transactionComplete(transaction);

      return result === undefined
        ? fallback
        : result.value;
    }

    async function putSetting(key, value) {
      const database = await databasePromise;
      const transaction = database.transaction(
        'settings',
        'readwrite'
      );

      transaction.objectStore('settings').put({
        key,
        value,
      });

      await transactionComplete(transaction);
    }

    async function packMetadata() {
      let metadata = await setting('pack', null);

      if (metadata === null) {
        metadata = {
          packId: crypto.randomUUID(),
          name: 'Custom Content',
        };

        await putSetting('pack', metadata);
      }

      return metadata;
    }

    async function contentPack() {
      const [metadata, entities] = await Promise.all([
        packMetadata(),
        allEntities(),
      ]);

      return {
        schemaVersion: 1,
        packId: metadata.packId,
        name: metadata.name,
        entities: entities
          .slice()
          .sort((left, right) => (
            left.contentId.localeCompare(
              right.contentId
            )
          ))
          .map((record) => ({
            contentId: record.contentId,
            kind: record.kind,
            definition: record.definition,
            implementation: (
              record.implementation
              || defaultImplementation()
            ),
          })),
      };
    }

    async function assetUrl(assetId) {
      if (typeof assetId !== 'string') {
        return null;
      }

      if (objectUrls.has(assetId)) {
        return objectUrls.get(assetId);
      }

      const database = await databasePromise;
      const transaction = database.transaction(
        'assets',
        'readonly'
      );
      const asset = await requestValue(
        transaction.objectStore('assets').get(
          assetId
        )
      );

      await transactionComplete(transaction);

      if (asset === undefined) {
        objectUrls.set(assetId, null);
        return null;
      }

      const url = URL.createObjectURL(asset.blob);
      objectUrls.set(assetId, url);
      return url;
    }

    function clientAssetId(record) {
      const image = record?.definition?.image;

      return image?.source === 'client'
        ? image.assetId
        : null;
    }

    function forgetAssetUrl(assetId) {
      const url = objectUrls.get(assetId);

      if (typeof url === 'string') {
        URL.revokeObjectURL(url);
      }

      objectUrls.delete(assetId);
    }

    function clearAssetUrls() {
      for (const assetId of [...objectUrls.keys()]) {
        forgetAssetUrl(assetId);
      }
    }

    async function restoreEditorBackup(backup) {
      if (
        !backup
        || backup.backupVersion !== 1
        || !Array.isArray(backup.editorEntities)
        || !Array.isArray(backup.assets)
      ) {
        throw new Error(
          'The selected file is not an editor backup.'
        );
      }

      const assets = backup.assets.map((asset) => ({
        assetId: asset.assetId,
        mimeType: asset.mimeType,
        blob: blobFromBase64(
          asset.data,
          asset.mimeType
        ),
      }));
      const metadata = {
        packId: backup.pack.packId,
        name: backup.pack.name,
      };

      const database = await databasePromise;
      const transaction = database.transaction(
        [
          'entities',
          'assets',
          'settings',
        ],
        'readwrite'
      );
      const entityStore = transaction.objectStore(
        'entities'
      );
      const assetStore = transaction.objectStore(
        'assets'
      );
      const settingsStore = transaction.objectStore(
        'settings'
      );

      entityStore.clear();
      assetStore.clear();

      for (const record of backup.editorEntities) {
        entityStore.put(record);
      }

      for (const asset of assets) {
        assetStore.put(asset);
      }

      settingsStore.put({
        key: 'pack',
        value: metadata,
      });
      settingsStore.put({
        key: 'initialBackupImported',
        value: true,
      });

      await transactionComplete(transaction);

      clearAssetUrls();
      state.selectedId = null;
      state.importPreview = null;
      contentChanged();
    }

    async function importInitialEditorBackup() {
      if (
        INITIAL_EDITOR_BACKUP === null
        || (
          await setting(
            'initialBackupImported',
            false
          )
        )
      ) {
        return;
      }

      if ((await allEntities()).length === 0) {
        await restoreEditorBackup(
          INITIAL_EDITOR_BACKUP
        );
      } else {
        await putSetting(
          'initialBackupImported',
          true
        );
      }
    }

    async function commitImport(preview) {
      const existing = new Map(
        (await allEntities()).map((record) => [
          record.importKey,
          record,
        ])
      );

      const records = [];
      const assets = [];
      const obsoleteAssetIds = new Set();

      for (const draft of preview.drafts) {
        const oldRecord = existing.get(draft.importKey);
        const oldAssetId = clientAssetId(oldRecord);
        let image = null;

        if (draft.image?.kind === 'existing') {
          image = {
            source: 'existing',
            name: draft.image.name,
          };
        } else if (draft.image?.kind === 'data') {
          const blob = await blobFromDataImage(draft.image);
          const assetId = crypto.randomUUID();

          assets.push({
            assetId,
            blob,
            mimeType: blob.type,
          });

          image = {
            source: 'client',
            assetId,
          };
        }

        if (oldAssetId !== null) {
          obsoleteAssetIds.add(oldAssetId);
        }

        const kindChanged = (
          oldRecord
          && oldRecord.kind !== draft.kind
        );

        records.push({
          contentId: (
            oldRecord?.contentId
            ?? crypto.randomUUID()
          ),
          importKey: draft.importKey,
          kind: draft.kind,
          definition: {
            ...draft.definition,
            image,
          },
          implementation: (
            oldRecord && !kindChanged
              ? (
                  oldRecord.implementation
                  || defaultImplementation()
                )
              : defaultImplementation()
          ),
          workspace: (
            oldRecord && !kindChanged
              ? oldRecord.workspace ?? null
              : null
          ),
          workspaceValid: (
            oldRecord && !kindChanged
              ? oldRecord.workspaceValid !== false
              : true
          ),
        });
      }

      const oldMetadata = (
        preview.name === null
          ? null
          : await packMetadata()
      );

      const database = await databasePromise;
      const transaction = database.transaction(
        [
          'entities',
          'assets',
          'settings',
        ],
        'readwrite'
      );
      const entityStore = transaction.objectStore(
        'entities'
      );
      const assetStore = transaction.objectStore(
        'assets'
      );

      for (const record of records) {
        entityStore.put(record);
      }

      for (const asset of assets) {
        assetStore.put(asset);
      }

      for (const assetId of obsoleteAssetIds) {
        assetStore.delete(assetId);
      }

      if (preview.name !== null) {
        transaction.objectStore('settings').put({
          key: 'pack',
          value: {
            ...oldMetadata,
            name: preview.name,
          },
        });
      }

      await transactionComplete(transaction);

      for (const assetId of obsoleteAssetIds) {
        forgetAssetUrl(assetId);
      }

      contentChanged();
    }

    async function deleteEntity(record) {
      const database = await databasePromise;
      const transaction = database.transaction(
        [
          'entities',
          'assets',
        ],
        'readwrite'
      );

      transaction.objectStore('entities').delete(
        record.contentId
      );

      const assetId = clientAssetId(record);

      if (assetId !== null) {
        transaction.objectStore('assets').delete(
          assetId
        );
      }

      await transactionComplete(transaction);

      if (assetId !== null) {
        forgetAssetUrl(assetId);
      }

      contentChanged();
    }

    async function saveWorkspace(showError = false) {
      if (
        state.workspace === null
        || state.workspaceEntityId === null
      ) {
        return true;
      }

      const record = await entityById(
        state.workspaceEntityId
      );

      if (record === undefined) {
        if (showError) {
          alert('The edited entity no longer exists.');
        }

        return false;
      }

      if (
        !state.workspaceChanged
        && !showError
      ) {
        return record.workspaceValid !== false;
      }

      record.workspace = (
        window.Blockly.serialization.workspaces.save(
          state.workspace
        )
      );

      try {
        record.implementation = workspaceProgram(
          state.workspace,
          record.kind
        );
        record.workspaceValid = true;

        await putEntity(record);

        state.workspaceChanged = false;
        contentChanged();
        return true;
      } catch (error) {
        record.workspaceValid = false;
        await putEntity(record);

        state.workspaceChanged = false;
        contentChanged();

        if (showError) {
          alert(
            error instanceof Error
              ? error.message
              : String(error)
          );

          if (typeof error?.blockId === 'string') {
            const block = state.workspace.getBlockById(
              error.blockId
            );

            if (block !== null) {
              state.workspace.centerOnBlock(block.id);
              block.select();
            }
          }
        }

        return false;
      }
    }

    function disposeWorkspace() {
      if (state.workspace !== null) {
        state.workspace.dispose();
      }

      state.workspace = null;
      state.workspaceEntityId = null;
      state.workspaceChanged = false;
    }

    function validationMessage(result) {
      const diagnostics = Array.isArray(
        result?.diagnostics
      )
        ? result.diagnostics
        : [];

      if (diagnostics.length === 0) {
        return 'Validation found errors.';
      }

      const shown = diagnostics
        .slice(0, 10)
        .map((diagnostic) => (
          `${diagnostic.code}: ${diagnostic.message}`
        ));

      if (diagnostics.length > shown.length) {
        shown.push(
          `${diagnostics.length - shown.length} more error(s).`
        );
      }

      return shown.join('\n');
    }

    async function runValidation() {
      if (!await saveWorkspace(true)) {
        return null;
      }

      const records = await allEntities();
      const invalidRecord = records.find(
        (record) => record.workspaceValid === false
      );

      if (invalidRecord !== undefined) {
        alert(
          `${invalidRecord.definition.name} has an invalid `
          + 'Blockly workspace. Open it and save a valid implementation.'
        );
        return null;
      }

      const pack = await contentPack();
      const result = await jsonRequest(
        options.httpUrl('/v1/content/validate'),
        {
          method: 'POST',
          body: JSON.stringify(pack),
        }
      );

      state.validation = result;

      if (result.valid) {
        storeCatalogPreview(result, pack.packId);
      } else {
        clearCatalogPreview();
      }

      return result;
    }

    async function navigate(tab, selectedId = null) {
      await saveWorkspace(false);
      disposeWorkspace();

      state.tab = tab;

      if (selectedId !== null) {
        state.selectedId = selectedId;
      }

      await render();
    }

    async function openWorkspace(record, host) {
      await loadBlockly();
      registerBlocklyBlocks();

      const workspace = window.Blockly.inject(
        host,
        {
          toolbox: blocklyToolbox(record.kind),
          theme: 'dark',
        }
      );

      workspace.dcEntityKind = record.kind;

      if (record.workspace) {
        try {
          restoreBlocklyWorkspace(
            workspace,
            record.workspace
          );
        } catch (error) {
          console.warn(
            'Could not restore Blockly workspace.',
            error
          );
          alert('Could not restore Blockly workspace. See console for details.');
        }
      } else {
        createRootBlock(workspace, record.kind);
      }

      state.workspace = workspace;
      state.workspaceEntityId = record.contentId;
      state.workspaceChanged = false;

      workspace.addChangeListener((event) => {
        if (!event.isUiEvent) {
          state.workspaceChanged = true;
        }
      });
    }

    function injectStyles() {
      if (
        document.getElementById('deltacards-content-editor-style')
      ) return;

      const style = element('style');
      style.id = 'deltacards-content-editor-style';

      style.textContent = `
        .dc-editor-overlay {
          position: fixed;
          inset: 0;
          z-index: 1005;
          background: rgba(0, 0, 0, 0.75);
          padding: 20px;
          box-sizing: border-box;
        }

        .dc-editor-window {
          width: 100%;
          height: 100%;
          background: #000;
          color: #fff;
          display: flex;
          flex-direction: column;
        }

        .dc-editor-header,
        .dc-editor-tabs,
        .dc-editor-actions {
          display: flex;
          gap: 8px;
          padding: 8px;
          align-items: center;
          flex-wrap: wrap;
        }

        .dc-editor-header {
          justify-content: space-between;
          background: #222;
          color: #fff;
        }

        .dc-editor-tabs {
          border-bottom: 1px solid #666;
        }

        .dc-editor-body {
          flex: 1;
          min-height: 0;
          overflow: auto;
          padding: 10px;
        }

        .dc-editor-button {
          padding: 6px 10px;
          border: 1px solid #888;
          border-radius: 3px;
          background: #292929;
          color: #fff;
          cursor: pointer;
        }

        .dc-editor-button:hover:not(:disabled) {
          background: #444;
          border-color: #aaa;
        }

        .dc-editor-button:disabled {
          background: #333;
          color: #888;
          cursor: not-allowed;
          opacity: 1;
        }

        .dc-editor-blockly {
          width: 100%;
          height: calc(100vh - 250px);
          min-height: 500px;
        }

        .dc-editor-card-grid {
          display: flex;
          align-items: flex-start;
          flex-wrap: wrap;
          gap: 16px;
        }

        .dc-editor-card-entry {
          width: 180px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 6px;
        }

        .dc-editor-card-entry .card {
          float: none;
          margin: 0;
        }

        .dc-editor-card-actions {
          display: flex;
          justify-content: center;
          gap: 6px;
        }

        .dc-editor-simple-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-width: 720px;
        }

        .dc-editor-simple-entry {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          border: 1px solid #555;
          padding: 8px;
        }

        .dc-editor-panel {
          border: 1px solid #666;
          padding: 8px;
          margin: 8px 0;
        }

        .dc-editor-panel pre {
          background: #111;
          border-color: #555;
          color: inherit;
          white-space: pre-wrap;
          overflow-wrap: anywhere;
        }

        .dc-editor-error {
          color: #ff7777;
        }

        .blocklyDropDownDiv,
        .blocklyWidgetDiv,
        .blocklyTooltipDiv {
          z-index: 1006 !important;
        }

        #toolbox-search-input {
          background: #252526;
          color: #fff;
          outline: none;
          color-scheme: dark;
        }
      `;

      document.head.append(style);
    }

    function ensureOverlay() {
      if (state.overlay !== null) {
        return;
      }

      injectStyles();

      const overlay = element('div', {
        className: 'dc-editor-overlay',
      });
      overlay.hidden = true;

      const windowElement = element('div', {
        className: 'dc-editor-window',
      });

      const title = element('strong', {
        text: 'deltacards Custom Content Editor',
      });

      const close = actionButton(
        'Close',
        async () => {
          await saveWorkspace(false);
          disposeWorkspace();
          overlay.hidden = true;
        }
      );

      const header = element(
        'div',
        {
          className: 'dc-editor-header',
        },
        title,
        close
      );

      const tabs = element('div', {
        className: 'dc-editor-tabs',
      });

      for (const [key, label] of [
        ['collection', 'Collection'],
        ['import', 'Import'],
        ['implementation', 'Implementation'],
        ['export', 'Export'],
        ['launch', 'Validate and launch'],
      ]) {
        tabs.append(
          actionButton(
            label,
            () => navigate(key)
          )
        );
      }

      const body = element('div', {
        className: 'dc-editor-body',
      });

      windowElement.append(
        header,
        tabs,
        body
      );
      overlay.append(windowElement);
      document.body.append(overlay);

      state.overlay = overlay;
      state.body = body;
    }

    function frontendStatusName(value) {
      if (value === 'KR') return value;

      return value
        .toLowerCase()
        .split('_')
        .map((word) => (
          word.charAt(0).toUpperCase()
          + word.slice(1)
        ))
        .join('');
    }

    function editorCardView(record, index) {
      const definition = record.definition;
      const assignedId = state.validation?.assignedIds?.[record.contentId];
      const fixedId = (
        Number.isInteger(assignedId)
          ? assignedId
          : 1_900_000_000 + index
      );
      const cost = Number.isInteger(definition.cost)
        ? definition.cost
        : 0;
      const rarity = CARD_RARITIES.has(definition.rarity)
        ? definition.rarity
        : 'BASE';

      const card = {
        id: `dc-editor-card-${index}`,
        fixedId,
        name: 'Custom Card',
        image: 'Dummy',
        baseImage: 'Dummy',
        extension: 'BASE',
        rarity,
        typeCard: record.kind === 'spell' ? 1 : 0,
        typeSkin: 0,
        shiny: false,
        cost,
        originalCost: cost,
        ownerId: 1,
        tribes: (
          record.kind === 'monster'
          && Array.isArray(definition.tribes)
            ? definition.tribes
            : []
        ),
        statuses: [
          ...(definition.keywords || []).map((keyword) => ({
            name: frontendStatusName(keyword),
            counter: 1,
          })),
          ...Object.entries(definition.statuses || {}).map(
            ([status, counter]) => ({
              name: frontendStatusName(status),
              counter,
            })
          ),
        ],
        frameSkinName: 'undertale',
      };

      if (record.kind === 'monster') {
        card.attack = Number.isInteger(definition.attack)
          ? definition.attack
          : 0;
        card.originalAttack = card.attack;
        card.hp = Number.isInteger(definition.hp)
          ? definition.hp
          : 1;
        card.maxHp = card.hp;
        card.originalHp = card.hp;
      } else if (
        typeof definition.soulId === 'string'
        && STANDARD_SOULS.includes(definition.soulId)
      ) {
        card.soul = {
          name: definition.soulId,
        };
      }

      return card;
    }

    async function editorImageUrl(record) {
      const image = record.definition.image;

      if (image?.source === 'client') {
        return assetUrl(image.assetId);
      }

      if (image?.source === 'existing') {
        return new URL(
          `/images/cards/${image.name}.png`,
          location.href
        ).href;
      }

      return null;
    }

    async function renderEditorCard(record, index) {
      const view = editorCardView(record, index);
      const card = window.appendCard(view, null);

      const nameContainer = card.find('.cardName div');
      const descriptionContainer = card.find('.cardDesc div');

      setEditorCardText(
        nameContainer[0],
        record.definition.name,
        false
      );
      setEditorCardText(
        descriptionContainer[0],
        record.definition.description,
        true
      );

      nameContainer[0].style.removeProperty('font-size');
      descriptionContainer[0].style.removeProperty('font-size');

      nameContainer.css(
        'font-size',
        window.getResizedFontSize(nameContainer, 25)
      );
      descriptionContainer.css(
        'font-size',
        window.getResizedFontSize(descriptionContainer, 81)
      );

      const imageUrl = await editorImageUrl(record);
      const imageElement = card.find('.cardImage')[0];

      if (imageUrl === null) {
        imageElement.style.backgroundImage = 'none';
      } else {
        imageElement.style.backgroundImage = `url("${imageUrl}")`;
        imageElement.style.backgroundRepeat = 'no-repeat';
        imageElement.style.backgroundSize = 'cover';
      }

      return card[0];
    }

    async function renderCollection() {
      const records = await allEntities();
      const cards = records.filter(
        (record) => (
          record.kind === 'monster'
          || record.kind === 'spell'
        )
      );
      const artifacts = records.filter(
        (record) => record.kind === 'artifact'
      );
      const enchantments = records.filter(
        (record) => record.kind === 'enchantment'
      );

      function entityActions(record) {
        return element(
          'div',
          {
            className: 'dc-editor-card-actions',
          },
          actionButton(
            'Edit',
            () => navigate(
              'implementation',
              record.contentId
            )
          ),
          actionButton(
            'Delete',
            async () => {
              if (
                !confirm(`Delete ${record.definition.name}?`)
              ) return;

              await deleteEntity(record);
              await render();
            }
          )
        );
      }

      const sections = [];

      if (cards.length > 0) {
        await loadCardRenderer();

        const grid = element('div', {
          className: 'dc-editor-card-grid cardsList',
        });

        for (
          const [index, record]
          of cards.entries()
        ) {
          const entry = element('div', {
            className: 'dc-editor-card-entry',
          });

          entry.append(
            await renderEditorCard(record, index),
            entityActions(record)
          );

          grid.append(entry);
        }

        sections.push(
          element('h2', {
            text: `Cards (${cards.length})`,
          }),
          grid
        );
      }

      for (const [kind, group] of [
        ['Artifacts', artifacts],
        ['Enchantments', enchantments],
      ]) {
        if (group.length === 0) continue;

        const list = element('div', {
          className: 'dc-editor-simple-list',
        });

        for (const record of group) {
          list.append(
            element(
              'div',
              {
                className: 'dc-editor-simple-entry',
              },
              element('strong', {
                text: record.definition.name,
              }),
              entityActions(record)
            )
          );
        }

        sections.push(
          element('h2', {
            text: `${kind} (${group.length})`,
          }),
          list
        );
      }

      if (sections.length === 0) {
        sections.push(
          element('p', {
            text: 'No custom entities have been imported.',
          })
        );
      }

      state.body.replaceChildren(...sections);
    }

    async function renderImport() {
      const fileInput = element('input', {
        type: 'file',
        accept: '.uceditor,.json,application/json',
      });

      const preview = element('div', {
        className: 'dc-editor-panel',
      });

      const backupFileInput = element('input', {
        type: 'file',
        accept: '.json,application/json',
      });

      async function showPreview() {
        preview.replaceChildren();

        if (state.importPreview === null) {
          preview.append(
            element('p', {
              text: 'Create custom content in the external editor and download a `.uceditor` file, then choose it here.',
            })
          );
          return;
        }

        for (const error of state.importPreview.errors) {
          preview.append(
            element('p', {
              className: 'dc-editor-error',
              text: `Error: ${error}`,
            })
          );
        }

        const existing = new Map(
          (await allEntities()).map((record) => [
            record.importKey,
            record,
          ])
        );

        for (const draft of state.importPreview.drafts) {
          preview.append(
            element('p', {
              text: (
                `${
                  existing.has(draft.importKey)
                    ? 'Update'
                    : 'Add'
                }: ${draft.definition.name} (${draft.kind})`
              ),
            })
          );
        }

        preview.append(
          actionButton(
            'Apply import',
            async () => {
              try {
                await commitImport(
                  state.importPreview
                );
                state.importPreview = null;
                await navigate('collection');
              } catch (error) {
                alert(error.message);
              }
            },
            state.importPreview.errors.length !== 0
          )
        );
      }

      fileInput.addEventListener(
        'change',
        async () => {
          const file = fileInput.files?.[0];

          if (!file) {
            return;
          }

          if (file.size > MAX_IMPORT_BYTES) {
            alert('The import file exceeds 8 MiB.');
            return;
          }

          try {
            state.importPreview = normalizeExternalExport(
              parseExternalEditorText(await file.text())
            );
          } catch (error) {
            state.importPreview = {
              name: null,
              drafts: [],
              errors: [
                `Could not parse the import: ${error.message}`,
              ],
            };
          }

          await showPreview();
        }
      );

      const editorLink = element('a', {
        text: 'Card editor by Sernon158',
      });
      editorLink.href = EXTERNAL_EDITOR_ORIGIN;
      editorLink.target = '_blank';

      const restoreBackup = actionButton(
        'Restore',
        async () => {
          const file = backupFileInput.files?.[0];

          if (!file) {
            alert('Choose an editor backup first.');
            return;
          }

          try {
            const backup = JSON.parse(
              await file.text()
            );

            if (
              !confirm(
                'Restoring this backup will replace every stored custom entity and image. Continue?'
              )
            ) {
              return;
            }

            await restoreEditorBackup(backup);
            await navigate('collection');
          } catch (error) {
            alert(error.message);
          }
        }
      );

      state.body.replaceChildren(
        element('h2', {
          text: 'Import custom content',
        }),
        element('h3', {
          text: 'Import from an external editor',
        }),
        element(
          'p',
          {},
          'Supported external editors: ',
          editorLink,
        ),
        fileInput,
        preview,
        element('hr'),
        element('h3', {
          text: 'Restore editor backup',
        }),
        element('p', {
          text: 'Warning: all custom content that is currently in the editor will be lost.',
        }),
        backupFileInput,
        element(
          'div',
          {
            className: 'dc-editor-actions',
          },
          restoreBackup
        )
      );

      await showPreview();
    }

    async function renderImplementation() {
      const records = await allEntities();

      if (
        state.selectedId === null
        || !records.some(
          (record) => (
            record.contentId === state.selectedId
          )
        )
      ) {
        state.selectedId = (
          records[0]?.contentId
          ?? null
        );
      }

      const selected = records.find(
        (record) => (
          record.contentId === state.selectedId
        )
      );

      if (!selected) {
        state.body.replaceChildren(
          element('p', {
            text: (
              'Import an entity before editing an implementation.'
            ),
          })
        );
        return;
      }

      const entitySelect = element('select', {
        value: selected.contentId,
      });

      for (const record of records) {
        const option = element('option', {
          value: record.contentId,
          text: `${record.definition.name} (${record.kind})`,
        });
        option.selected = (
          record.contentId === selected.contentId
        );
        entitySelect.append(option);
      }

      entitySelect.addEventListener('change', () => {
        void navigate(
          'implementation',
          entitySelect.value
        );
      });

      const host = element('div', {
        className: 'dc-editor-blockly',
      });

      const save = actionButton(
        'Save',
        async () => {
          if (await saveWorkspace(true)) {
            alert('Saved.');
          }
        }
      );

      state.body.replaceChildren(
        element(
          'div',
          {
            className: 'dc-editor-actions',
          },
          entitySelect,
          save,
        ),
        host
      );

      await openWorkspace(selected, host);
    }

    async function renderExport() {
      const [pack, records] = await Promise.all([
        contentPack(),
        allEntities(),
      ]);

      state.body.replaceChildren(
        element('h2', {
          text: 'Export',
        }),
        element('p', {
          text: `${pack.entities.length} custom entities are stored.`,
        }),
        element(
          'div',
          {
            className: 'dc-editor-actions',
          },
          actionButton(
            'Export content pack',
            () => downloadJson(
              'deltacards-pack.json',
              pack
            )
          ),
          actionButton(
            'Export editor backup',
            async () => {
              try {
                downloadJson(
                  'deltacards-editor-backup.json',
                  {
                    backupVersion: 1,
                    pack,
                    editorEntities: records,
                    assets: await backupAssets(),
                  }
                );
              } catch (error) {
                alert(
                  `Could not export the editor backup: ${error.message}`
                );
              }
            }
          )
        )
      );
    }

    async function renderLaunch() {
      const pack = await contentPack();

      const validate = actionButton(
        'Validate',
        async () => {
          try {
            const result = await runValidation();

            if (result === null) {
              return;
            }

            alert(
              result.valid
                ? 'The custom content collection is valid.'
                : validationMessage(result)
            );
          } catch (error) {
            alert(error.message);
          }
        }
      );

      const openDecks = actionButton(
        'Validate and open Decks page',
        async () => {
          if (
            typeof options.isCustomContentEverywhereEnabled !== 'function'
            || !options.isCustomContentEverywhereEnabled()
          ) {
            alert(
              'Enable "Load custom content everywhere except in online games" '
              + 'to be able to see custom content on the Decks page.'
            );
            return;
          }

          try {
            const result = await runValidation();

            if (result === null) {
              return;
            }

            if (!result.valid) {
              alert(validationMessage(result));
              return;
            }

            location.assign('/Decks');
          } catch (error) {
            alert(error.message);
          }
        }
      );

      const launch = actionButton(
        'Create CPU match',
        async () => {
          try {
            const validation = await runValidation();

            if (validation === null) {
              return;
            }

            if (!validation.valid) {
              alert(validationMessage(validation));
              return;
            }

            if (typeof options.getDeck !== 'function') {
              throw new Error(
                'The bridge did not provide a configured deck.'
              );
            }

            const deck = String(
              options.getDeck() ?? ''
            ).trim();

            const result = await jsonRequest(
              options.httpUrl('/v1/games'),
              {
                method: 'POST',
                body: JSON.stringify({
                  pack: await contentPack(),
                  deck,
                }),
              }
            );

            options.onLaunch(result);
          } catch (error) {
            alert(error.message);
          }
        }
      );

      state.body.replaceChildren(
        element('h2', {
          text: 'Validate and launch',
        }),
        element('p', {
          text: (
            `${pack.entities.length} custom entities are stored.`
          ),
        }),
        element(
          'ol',
          {},
          element(
            'li',
            {},
            '(optional) Open the Decks page, build and export a deck there.'
          ),
          element(
            'li',
            {},
            '(optional) Paste that code into the plugin setting "Your deck code".'
          ),
          element(
            'li',
            {},
            'Return here and start the match.'
          )
        ),
        element(
          'div',
          {
            className: 'dc-editor-actions',
          },
          validate,
          openDecks,
          launch
        )
      );
    }

    async function render() {
      if (state.body === null) {
        return;
      }

      disposeWorkspace();

      if (state.tab === 'collection') {
        await renderCollection();
      } else if (state.tab === 'import') {
        await renderImport();
      } else if (state.tab === 'implementation') {
        await renderImplementation();
      } else if (state.tab === 'export') {
        await renderExport();
      } else {
        await renderLaunch();
      }
    }

    async function waitForBody() {
      if (document.body !== null) {
        return;
      }

      await new Promise((resolve) => {
        document.addEventListener(
          'DOMContentLoaded',
          resolve,
          {
            once: true,
          }
        );
      });
    }

    function closeUnderScriptDialog() {
      const modal = document.querySelector(
        '.modal.bootstrap-dialog.underscript-dialog:is(.in, .show)'
      );

      window.BootstrapDialog?.dialogs?.[modal?.id]?.close();
    }

    async function open() {
      try {
        await Promise.all([
          databasePromise,
          waitForBody(),
        ]);

        await importInitialEditorBackup();

        closeUnderScriptDialog();

        ensureOverlay();
        state.overlay.hidden = false;
        await render();
      } catch (error) {
        console.error(
          'Could not open the Custom Content Editor.',
          error
        );
        alert(
          `Could not open the Custom Content Editor: ${error.message}`
        );
      }
    }

    window.addEventListener('unload', () => {
      clearAssetUrls();
    });

    return {
      ready: databasePromise.then(() => undefined),
      open,
      assetUrl,
    };
  }

  window.deltacardsContentEditor = {
    create,
  };
})();
