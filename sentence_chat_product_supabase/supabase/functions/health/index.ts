import { handleRequest } from "../_shared/router.ts";

Deno.serve((req) => handleRequest(req, "/health"));
