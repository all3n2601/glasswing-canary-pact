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
    exports, URL, Response, Headers, AbortSignal, Error, TypeError, DOMException, process: { env: {} },
    require: (name) => {
      if (Object.hasOwn(dependencies, name)) return dependencies[name];
      if (name === "react/jsx-runtime") return require(name);
      throw new Error(`Unexpected dependency: ${name}`);
    },
    ...globals,
  }, { filename });
  return exports;
}

function transport(fetch, env={}) {
  const warnings=[];
  const module=load("lib/canary-api-transport.ts",{"server-only":{}},{
    fetch,process:{env},console:{warn:(...args)=>warnings.push(args)},
    setTimeout:callback=>{queueMicrotask(callback);return 1;},
  });
  return {...module,warnings};
}

function session({ token, status = 200, offline = false, statuses } = {}) {
  let requests = 0;
  const user = { user_id: "usr_test", display_name: "Test viewer", role: "viewer" };
  const fetch=async (_url, init) => {
    requests++;
    assert.equal(init.headers.Authorization, `Bearer ${token}`);
    assert.equal(init.cache, "no-store");
    if (offline) throw new TypeError("Connection refused");
    return Response.json(user, { status:statuses?.[requests-1] ?? status });
  };
  const auth = load("lib/auth-server.ts", {
    "server-only": {},
    "./canary-api-transport": transport(fetch),
    "react": { cache: (fn) => fn },
    "next/headers": { cookies: async () => ({ get: () => token ? { value: token } : undefined }) },
    "next/navigation": { redirect: (url) => { throw new Error(`REDIRECT:${url}`); } },
    "next/server": { NextResponse: Response },
  }, {
    fetch,
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
    "@/lib/canary-api-transport": { API_URL:"http://localhost:8000" },
  }, { fetch: () => { throw new Error("Unauthenticated request was forwarded"); } });
  for (const [method, path] of [["GET", "organization/profile"], ["POST", "simulate/quick"]]) {
    const response = await route[method](new Request(`http://localhost/api/canary/${path}`, { method }), {
      params: Promise.resolve({ path: path.split("/") }),
    });
    assert.equal(response.status, 401);
  }
});

test("server account verification recovers from a transient outage but never retries invalid sessions",async()=>{
  const recovering=session({token:"existing",statuses:[503,200]});
  assert.equal((await recovering.auth.requireUser("/simulate")).user_id,"usr_test");
  assert.equal(recovering.requests(),2);
  const expired=session({token:"expired",status:401});
  assert.equal((await expired.auth.getSession()).user,null);
  assert.equal(expired.requests(),1);
});

test("server reads retry timeouts and network failures once, without caching users or exposing credentials",async()=>{
  for (const error of [new DOMException("Timed out","TimeoutError"),new TypeError("Connection reset")]) {
    const headers=[];
    const api=transport(async(url,init)=>{
      headers.push(init.headers.Authorization);
      assert.equal(init.cache,"no-store");
      assert.ok(init.signal);
      if(headers.length===1) throw error;
      return Response.json({ok:true});
    });
    assert.equal((await api.readBackend("/auth/me",{Authorization:"Bearer first"})).status,200);
    await api.readBackend("/auth/me",{Authorization:"Bearer second"});
    assert.deepEqual(headers,["Bearer first","Bearer first","Bearer second"]);
  }
  let attempts=0;
  const failed=transport(async()=>{attempts++;throw new TypeError("secret backend URL and credentials");});
  await assert.rejects(failed.readBackend("/auth/me",{Authorization:"Bearer private"}));
  assert.equal(attempts,2);
  assert.doesNotMatch(JSON.stringify(failed.warnings),/secret|credentials|private/);
  assert.match(JSON.stringify(failed.warnings),/\/auth\/me/);
});

test("blank server API configuration uses the public fallback and removes trailing slashes",()=>{
  const api=transport(()=>{}, {CANARY_API_URL:"  ",NEXT_PUBLIC_API_URL:"https://backend.example///"});
  assert.equal(api.API_URL,"https://backend.example");
});

test("profile and agent-skill page reads recover from 503 while retaining their session headers",async()=>{
  const calls={};
  const api=transport(async(url,init)=>{
    assert.equal(init.headers.Authorization,"Bearer existing");
    calls[url]=(calls[url]??0)+1;
    if(calls[url]===1) return Response.json({detail:"Busy"},{status:503});
    return Response.json(url.endsWith("agent-skills") ? [] : {twin_version:"saved_baseline"});
  });
  const pages=load("lib/canary-api-server.ts",{
    "server-only":{},"./auth-server":{authToken:async()=>"existing"},
    "./canary-api-transport":api,"./organization-profile":{normalizeProfile:value=>value},
  });
  assert.equal((await pages.getOrganizationProfile()).twin_version,"saved_baseline");
  assert.equal((await pages.getAgentSkillFiles()).length,0);
  assert.deepEqual(Object.values(calls),[2,2]);
});

test("auth writes are never retried when their response is lost",async()=>{
  const {auth,requests}=session({token:"existing",offline:true});
  await assert.rejects(auth.callAuthApi("/login",{method:"POST",headers:{Authorization:"Bearer existing"}}));
  assert.equal(requests(),1);
});

test("unavailable page offers a route refresh and exposes retry progress",()=>{
  const React=require("react");
  const {renderToStaticMarkup}=require("react-dom/server");
  let refreshes=0;
  const makePage=pending=>load("components/backend-unavailable.tsx",{
    react:{useTransition:()=>[pending,fn=>fn()]},
    "next/navigation":{useRouter:()=>({refresh:()=>refreshes++})},
    "next/link":{default:props=>React.createElement("a",props)},
    "lucide-react":{AlertTriangle:()=>null,ArrowLeft:()=>null,RefreshCw:()=>null},
    "@/components/site-header":{SiteHeader:()=>null},
    "@/components/ui/button":{Button:({asChild,...props})=>asChild ? props.children : React.createElement("button",props)},
  }).BackendUnavailable;
  const Page=makePage(false);
  const tree=Page({resource:"account verification"});
  const html=renderToStaticMarkup(tree);
  assert.match(html,/Try again/);assert.match(html,/account verification/);
  assert.doesNotMatch(html,/API is unavailable|mock result/);
  const visit=node=>{
    if(Array.isArray(node)) return node.forEach(visit);
    if(!node?.props) return;
    if(node.props.onClick) node.props.onClick();
    visit(node.props.children);
  };
  visit(tree);assert.equal(refreshes,1);
  const pending=renderToStaticMarkup(React.createElement(makePage(true)));
  assert.match(pending,/disabled/);assert.match(pending,/Reconnecting to your workspace/);
});
