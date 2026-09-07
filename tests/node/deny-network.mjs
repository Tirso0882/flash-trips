const liveFetch = globalThis.fetch;
const localHosts = new Set(["127.0.0.1", "::1", "localhost"]);

globalThis.fetch = async (input, init) => {
  const url = new URL(input instanceof Request ? input.url : input);
  if (!localHosts.has(url.hostname)) {
    throw new Error(`Live network access is disabled in tests: ${url.hostname}`);
  }
  return liveFetch(input, init);
};
