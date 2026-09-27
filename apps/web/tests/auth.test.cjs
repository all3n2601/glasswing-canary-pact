const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

// Run the actual TypeScript with request-local Next/HTTP boundaries replaced.
// No running server, real account, or additional test framework is required.
function load(file, dependencies = {}, globals = {}) {
  const filename = resolve(__dirname, "..", file);
  const { outputText } = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  });
  const exports = {};
  vm.runInNewContext(outputText, {
    exports, URL, Response, Headers, AbortSignal, process: { env: {} },
    require: (name) => {
      if (Object.hasOwn(dependencies, name)) return dependencies[name];
      if (name === "react/jsx-runtime") return require(name);
      throw new Error(`Unexpected dependency: ${name}`);
    },
    ...globals,
  }, { filename });
  return exports;
}

function session({ token, status = 200, offline = false } = {}) {
  let requests = 0;
  const user = { user_id: "usr_test", display_name: "Test viewer", role: "viewer" };
  const auth = load("lib/auth-server.ts", {
    "server-only": {},
    "react": { cache: (fn) => fn },
    "next/headers": { cookies: async () => ({ get: () => token ? { value: token } : undefined }) },
    "next/navigation": { redirect: (url) => { throw new Error(`REDIRECT:${url}`); } },
    "next/server": { NextResponse: Response },
  }, {
    fetch: async (_url, init) => {
      requests++;
      assert.equal(init.headers.Authorization, `Bearer ${token}`);
      assert.equal(init.cache, "no-store");
      if (offline) throw new Error("Connection refused");
      return Response.json(user, { status });
    },
  });
  return { auth, user, requests: () => requests };
}

test("missing sessions redirect without contacting the API", async () => {
  const { auth, requests } = session();
  await assert.rejects(auth.requireUser("/simulate"), /REDIRECT:\/login\?next=%2Fsimulate/);
  assert.equal(requests(), 0);
});

test("a verified session opens the workspace; invalid or expired sessions redirect", async () => {
  const { auth, user } = session({ token: "valid" });
  assert.equal((await auth.requireUser("/simulate")).user_id, user.user_id);
  await assert.rejects(session({ token: "expired", status: 401 }).auth.requireUser("/simulate"), /REDIRECT:/);
});

test("outages do not redirect users back through login", async () => {
  for (const options of [{ status: 503 }, { offline: true }]) {
    const { auth } = session({ token: "existing", ...options });
    assert.equal(await auth.requireUser("/simulate"), null);
    assert.equal((await auth.getSession()).unavailable, true);
  }
});

test("return destinations stay local and cannot loop through authentication", () => {
  const { safeReturnTo } = load("lib/auth.ts");
  for (const value of [undefined, "https://example.com", "//example.com", "/\\example.com", "/\n/example.com", "/login", "/signup?next=/login", "/api/auth/logout", "/foo/../login"]) {
    assert.equal(safeReturnTo(value), "/simulate", String(value));
  }
  assert.equal(safeReturnTo("/evidence?run=run_test"), "/evidence?run=run_test");
});

for (const route of ["simulate", "compare", "evidence", "story", "onboarding", "settings/organization", "account"]) {
  test(`${route} verifies access before rendering or fetching data`, async () => {
    let checks = 0;
    const dependencies = new Proxy({
      "@/lib/auth-server": { requireUser: async (path) => { checks++; assert.equal(path, `/${route}`); throw new Error("REDIRECT"); } },
    }, {
      getOwnPropertyDescriptor: () => ({ configurable: true, enumerable: true }),
      get: (target, key) => target[key] ?? new Proxy({}, { get: () => () => { throw new Error("Private data was accessed"); } }),
    });
    const page = load(`app/${route}/page.tsx`, dependencies).default;
    await assert.rejects(page(), /^Error: REDIRECT$/);
    assert.equal(checks, 1);
  });
}

for (const mode of ["login", "signup"]) {
  test(`${mode} sends existing sessions to the requested workspace page`, async () => {
    const { safeReturnTo } = load("lib/auth.ts");
    const page = load(`app/${mode}/page.tsx`, {
      "next/navigation": { redirect: (url) => { throw new Error(`REDIRECT:${url}`); } },
      "@/lib/auth-server": { getSession: async () => ({ user: { user_id: "usr_test" }, unavailable: false }) },
      "@/lib/auth": { safeReturnTo },
      "@/components/backend-unavailable": {},
      "@/components/auth-form": {},
    }).default;
    await assert.rejects(page({ searchParams: Promise.resolve({ next: "/evidence" }) }), /REDIRECT:\/evidence/);
  });
}

test("workspace proxy rejects unauthenticated reads and writes without forwarding", async () => {
  const route = load("app/api/canary/[...path]/route.ts", {
    "next/server": { NextResponse: Response },
    "@/lib/auth-server": { getSession: async () => ({ user: null, unavailable: false }) },
  }, { fetch: () => { throw new Error("Unauthenticated request was forwarded"); } });
  for (const [method, path] of [["GET", "organization/profile"], ["POST", "simulate/quick"]]) {
    const response = await route[method](new Request(`http://localhost/api/canary/${path}`, { method }), {
      params: Promise.resolve({ path: path.split("/") }),
    });
    assert.equal(response.status, 401);
  }
});
