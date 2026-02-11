import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

type PleaStage =
  | "first_stage"
  | "after_first_stage_before_trial"
  | "day_of_trial"
  | "after_trial_begins"
  | "not_guilty";

type SentenceType =
  | "conditional_discharge"
  | "fine"
  | "community_order"
  | "youth_rehabilitation_order"
  | "determinate_custodial_sentence"
  | "suspended_sentence_order"
  | "dto"
  | "yoi_detention"
  | "extended_sentence"
  | "special_custodial_sentence"
  | "discretionary_life_sentence"
  | "mandatory_life_sentence";

type OffenceRecord = {
  offence_id: string;
  canonical_name: string;
  short_name: string;
  offence_category: string;
  provision: string;
  guideline_url: string;
  legislation_url: string;
  maximum_sentence_type: string;
  maximum_sentence_amount: string;
  minimum_sentence_code: string;
  specified_violent: boolean;
  specified_sexual: boolean;
  specified_terrorist: boolean;
  listed_offence: boolean;
  schedule18a_offence: boolean;
  schedule19za: boolean;
  cta_notification: boolean;
};

type SentencingRangeOut = {
  culpability: string;
  harm: string;
  starting_point_text: string;
  category_range_text: string;
};

type CalculateSentenceRequest = {
  offence_id?: string | null;
  offence_query?: string | null;
  offence_date: string;
  conviction_date: string;
  sentence_date: string;
  age_at_offence: number;
  age_at_conviction: number;
  age_at_sentence: number;
  plea_stage: PleaStage;
  sentence_type: SentenceType;
  culpability?: string | null;
  harm?: string | null;
  pre_plea_term_months?: number | null;
  extension_months?: number;
  fine_amount?: number | null;
  dangerousness_assessed?: boolean;
  prior_listed_offence_with_custody?: boolean;
  prior_domestic_burglary_count?: number;
  prior_class_a_trafficking_count?: number;
  prior_relevant_weapon_conviction?: boolean;
  terrorism_flag?: boolean;
  minimum_sentence_unjust_or_exceptional?: boolean;
  replicate_ace_release_bug?: boolean;
};

type CalculateSentenceResponse = {
  offence_id: string;
  offence_name: string;
  sentence_type: string;
  pre_plea_term_months: number | null;
  post_plea_term_months: number | null;
  minimum_sentence_triggered: boolean;
  minimum_floor_pre_plea_months: number | null;
  minimum_floor_post_plea_months: number | null;
  release_fraction: number | null;
  estimated_time_in_custody_months: number | null;
  victim_surcharge_gbp: number;
  matched_range: SentencingRangeOut | null;
  warnings: string[];
  trace: string[];
};

type SearchGuidelinesRequest = {
  query: string;
  offence_id?: string | null;
  top_k?: number;
};

type GuidelineChunkOut = {
  chunk_id: string;
  guideline_id: string;
  offence_id: string | null;
  section_type: string | null;
  section_heading: string | null;
  chunk_text: string;
  source_url: string | null;
  score: number | null;
};

type ChatTurnRequest = {
  message: string;
  offence_id?: string | null;
  offence_query?: string | null;
  calculation?: CalculateSentenceRequest | null;
  top_k?: number;
};

type ChatTurnResponse = {
  reply: string;
  calculation: CalculateSentenceResponse | null;
  citations: GuidelineChunkOut[];
  follow_up_questions: string[];
};

type ValidationItem = {
  loc: (string | number)[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
};

type MinimumSentenceDecision = {
  triggered: boolean;
  floor_pre_months: number | null;
  floor_post_months: number | null;
  reason: string | null;
};

type ReleaseDecision = {
  release_fraction: number | null;
  reason: string;
};

type SentenceCalculationInput = {
  offence: OffenceRecord;
  offence_date: Date;
  conviction_date: Date;
  sentence_date: Date;
  age_at_offence: number;
  age_at_conviction: number;
  age_at_sentence: number;
  plea_stage: PleaStage;
  sentence_type: SentenceType;
  culpability: string | null;
  harm: string | null;
  pre_plea_term_months: number | null;
  extension_months: number;
  fine_amount: number | null;
  dangerousness_assessed: boolean;
  prior_listed_offence_with_custody: boolean;
  prior_domestic_burglary_count: number;
  prior_class_a_trafficking_count: number;
  prior_relevant_weapon_conviction: boolean;
  terrorism_flag: boolean;
  minimum_sentence_unjust_or_exceptional: boolean;
  replicate_ace_release_bug: boolean;
};

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
};

const PLEA_FACTORS: Record<PleaStage, number> = {
  first_stage: 2 / 3,
  after_first_stage_before_trial: 3 / 4,
  day_of_trial: 9 / 10,
  after_trial_begins: 19 / 20,
  not_guilty: 1,
};

const CUSTODIAL_SENTENCE_TYPES = new Set<SentenceType>([
  "determinate_custodial_sentence",
  "dto",
  "yoi_detention",
  "extended_sentence",
  "special_custodial_sentence",
  "discretionary_life_sentence",
  "mandatory_life_sentence",
]);

const SUSPENDED_OR_NON_IMMEDIATE = new Set<SentenceType>([
  "suspended_sentence_order",
]);

const SERIOUS_PROVISION_MARKERS = [
  "manslaughter",
  "soliciting to commit murder",
  "grievous bodily harm with intent",
  "wounding with intent",
  "gbh with intent",
];

const FORTY_PERCENT_EXCLUSIONS = [
  "serious crime act 2015 s.76",
  "serious crime act 2015 s.75a",
  "sentencing act 2020 s.363",
  "family law act 1996 s.42a",
  "domestic abuse act 2021 s.39",
  "national security act",
  "official secrets act",
];

const PLEA_STAGE_VALUES = new Set<PleaStage>([
  "first_stage",
  "after_first_stage_before_trial",
  "day_of_trial",
  "after_trial_begins",
  "not_guilty",
]);

const SENTENCE_TYPE_VALUES = new Set<SentenceType>([
  "conditional_discharge",
  "fine",
  "community_order",
  "youth_rehabilitation_order",
  "determinate_custodial_sentence",
  "suspended_sentence_order",
  "dto",
  "yoi_detention",
  "extended_sentence",
  "special_custodial_sentence",
  "discretionary_life_sentence",
  "mandatory_life_sentence",
]);

const ENV = {
  supabaseUrl: Deno.env.get("SUPABASE_URL") ?? "",
  supabaseServiceRoleKey: Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "",
  openaiApiKey: Deno.env.get("OPENAI_API_KEY") ?? "",
  openaiEmbeddingModel: Deno.env.get("OPENAI_EMBEDDING_MODEL") ??
    "text-embedding-3-small",
  retrievalTopK: Number(Deno.env.get("RETRIEVAL_TOP_K") ?? "6"),
  enableVectorSearch:
    (Deno.env.get("ENABLE_VECTOR_SEARCH") ?? "true").toLowerCase() === "true",
};

if (!ENV.supabaseUrl || !ENV.supabaseServiceRoleKey) {
  throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set");
}

const supabase = createClient(ENV.supabaseUrl, ENV.supabaseServiceRoleKey, {
  auth: { persistSession: false },
});

export async function handleRequest(
  req: Request,
  forcedRoute?: string,
): Promise<Response> {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  try {
    const url = new URL(req.url);
    const route = forcedRoute ?? extractRoute(url.pathname);

    if (req.method === "GET" && route === "/health") {
      return jsonResponse({ status: "ok" }, 200);
    }

    if (req.method === "POST" && route === "/calculate_sentence") {
      const body = await parseJsonBody(req);
      const parsed = validateCalculateSentenceRequest(body, ["body"]);
      if (parsed.errors.length) {
        return validationResponse(parsed.errors);
      }
      const result = await calculateFromRequest(parsed.value);
      return jsonResponse(result, 200);
    }

    if (req.method === "POST" && route === "/search_guidelines") {
      const body = await parseJsonBody(req);
      const parsed = validateSearchGuidelinesRequest(body, ["body"]);
      if (parsed.errors.length) {
        return validationResponse(parsed.errors);
      }
      const rows = await searchGuidelines(
        parsed.value.query,
        parsed.value.offence_id ?? null,
        parsed.value.top_k,
      );
      return jsonResponse({ results: convertChunks(rows) }, 200);
    }

    if (req.method === "POST" && route === "/chat_turn") {
      const body = await parseJsonBody(req);
      const parsed = validateChatTurnRequest(body, ["body"]);
      if (parsed.errors.length) {
        return validationResponse(parsed.errors);
      }

      const reqBody = parsed.value;
      const followUp: string[] = [];
      let calcResponse: CalculateSentenceResponse | null = null;
      let offenceId = reqBody.offence_id ?? null;

      if (reqBody.calculation) {
        let calcReq = { ...reqBody.calculation };
        if (!calcReq.offence_id && offenceId) {
          calcReq = { ...calcReq, offence_id: offenceId };
        }
        if (
          !calcReq.offence_id && !calcReq.offence_query && reqBody.offence_query
        ) {
          calcReq = { ...calcReq, offence_query: reqBody.offence_query };
        }
        calcResponse = await calculateFromRequest(calcReq);
        offenceId = calcResponse.offence_id;
      } else if (!offenceId && !reqBody.offence_query) {
        followUp.push(
          "Which offence is this for? Provide offence_id or offence name.",
        );
      }

      const rows = await searchGuidelines(
        reqBody.message,
        offenceId,
        reqBody.top_k,
      );
      const citations = convertChunks(rows);

      if (followUp.length) {
        const payload: ChatTurnResponse = {
          reply: "I need one more detail before I can calculate a sentence.",
          calculation: calcResponse,
          citations,
          follow_up_questions: followUp,
        };
        return jsonResponse(payload, 200);
      }

      const replyParts: string[] = [];
      if (calcResponse) {
        replyParts.push(
          `Calculated sentence for ${calcResponse.offence_name}: post-plea term ${calcResponse.post_plea_term_months} months, estimated custody served ${calcResponse.estimated_time_in_custody_months} months, victim surcharge £${calcResponse.victim_surcharge_gbp}.`,
        );
        if (calcResponse.warnings.length) {
          replyParts.push(`Warnings: ${calcResponse.warnings.join(" ")}`);
        }
      }

      if (citations.length > 0) {
        const top = citations[0];
        replyParts.push(
          `Top supporting guideline section: ${
            top.section_heading ?? top.section_type ?? "section"
          } (${top.source_url ?? "no-url"}).`,
        );
      } else {
        replyParts.push("No guideline citation found for this query.");
      }

      const payload: ChatTurnResponse = {
        reply: replyParts.join("\n\n"),
        calculation: calcResponse,
        citations,
        follow_up_questions: [],
      };

      return jsonResponse(payload, 200);
    }

    return jsonResponse({ detail: "Not Found" }, 404);
  } catch (error) {
    if (isHttpError(error)) {
      return jsonResponse({ detail: error.detail }, error.statusCode);
    }
    const message = error instanceof Error ? error.message : "Unexpected error";
    return jsonResponse({ detail: message }, 500);
  }
}

if (import.meta.main) {
  Deno.serve((req) => handleRequest(req));
}

async function parseJsonBody(req: Request): Promise<unknown> {
  try {
    return await req.json();
  } catch {
    throw httpError(400, "Invalid JSON body");
  }
}

function extractRoute(pathname: string): string {
  const trimmed = pathname.replace(/\/+$/, "") || "/";
  if (
    trimmed.startsWith("/health") ||
    trimmed.startsWith("/calculate_sentence") ||
    trimmed.startsWith("/search_guidelines") ||
    trimmed.startsWith("/chat_turn")
  ) {
    return trimmed;
  }

  // When this shared handler is served directly, support
  // /functions/v1/<function-name>/<route>.
  const marker = "/functions/v1/";
  const markerIdx = trimmed.indexOf(marker);
  if (markerIdx !== -1) {
    const after = trimmed.slice(markerIdx + marker.length);
    const slashIdx = after.indexOf("/");
    if (slashIdx !== -1) {
      return after.slice(slashIdx);
    }
  }

  return trimmed;
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...CORS_HEADERS,
      "content-type": "application/json",
    },
  });
}

function validationResponse(detail: ValidationItem[]): Response {
  return jsonResponse({ detail }, 422);
}

function httpError(statusCode: number, detail: string) {
  return { statusCode, detail, _tag: "http_error" as const };
}

function isHttpError(
  value: unknown,
): value is { statusCode: number; detail: string; _tag: "http_error" } {
  return typeof value === "object" && value !== null && "_tag" in value;
}

function err(
  loc: (string | number)[],
  msg: string,
  type = "value_error",
  input?: unknown,
): ValidationItem {
  return { loc, msg, type, input };
}

function ensureObject(
  value: unknown,
  loc: (string | number)[],
): { errors: ValidationItem[]; value?: Record<string, unknown> } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return {
      errors: [
        err(loc, "Input should be an object", "type_error.object", value),
      ],
    };
  }
  return { errors: [], value: value as Record<string, unknown> };
}

function forbidUnknownKeys(
  obj: Record<string, unknown>,
  allowed: Set<string>,
  loc: (string | number)[],
): ValidationItem[] {
  const errors: ValidationItem[] = [];
  for (const key of Object.keys(obj)) {
    if (!allowed.has(key)) {
      errors.push(
        err(
          [...loc, key],
          "Extra inputs are not permitted",
          "extra_forbidden",
          obj[key],
        ),
      );
    }
  }
  return errors;
}

function parseDate(value: unknown): Date | null {
  if (typeof value !== "string") return null;
  const d = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function validateCalculateSentenceRequest(
  value: unknown,
  loc: (string | number)[],
): { errors: ValidationItem[]; value: CalculateSentenceRequest } {
  const base = ensureObject(value, loc);
  if (base.errors.length || !base.value) {
    return { errors: base.errors, value: {} as CalculateSentenceRequest };
  }

  const obj = base.value;
  const allowed = new Set([
    "offence_id",
    "offence_query",
    "offence_date",
    "conviction_date",
    "sentence_date",
    "age_at_offence",
    "age_at_conviction",
    "age_at_sentence",
    "plea_stage",
    "sentence_type",
    "culpability",
    "harm",
    "pre_plea_term_months",
    "extension_months",
    "fine_amount",
    "dangerousness_assessed",
    "prior_listed_offence_with_custody",
    "prior_domestic_burglary_count",
    "prior_class_a_trafficking_count",
    "prior_relevant_weapon_conviction",
    "terrorism_flag",
    "minimum_sentence_unjust_or_exceptional",
    "replicate_ace_release_bug",
  ]);

  const errors = forbidUnknownKeys(obj, allowed, loc);

  const required = [
    "offence_date",
    "conviction_date",
    "sentence_date",
    "age_at_offence",
    "age_at_conviction",
    "age_at_sentence",
    "plea_stage",
    "sentence_type",
  ];
  for (const key of required) {
    if (!(key in obj)) {
      errors.push(err([...loc, key], "Field required", "missing"));
    }
  }

  const offence_id = obj.offence_id == null
    ? null
    : typeof obj.offence_id === "string"
    ? obj.offence_id
    : undefined;
  const offence_query = obj.offence_query == null
    ? null
    : typeof obj.offence_query === "string"
    ? obj.offence_query
    : undefined;

  if (obj.offence_id != null && typeof obj.offence_id !== "string") {
    errors.push(
      err(
        [...loc, "offence_id"],
        "Input should be a valid string",
        "string_type",
        obj.offence_id,
      ),
    );
  }
  if (obj.offence_query != null && typeof obj.offence_query !== "string") {
    errors.push(
      err(
        [...loc, "offence_query"],
        "Input should be a valid string",
        "string_type",
        obj.offence_query,
      ),
    );
  }

  const offenceDate = parseDate(obj.offence_date);
  const convictionDate = parseDate(obj.conviction_date);
  const sentenceDate = parseDate(obj.sentence_date);

  if (!offenceDate) {
    errors.push(
      err(
        [...loc, "offence_date"],
        "Input should be a valid date",
        "date_type",
        obj.offence_date,
      ),
    );
  }
  if (!convictionDate) {
    errors.push(
      err(
        [...loc, "conviction_date"],
        "Input should be a valid date",
        "date_type",
        obj.conviction_date,
      ),
    );
  }
  if (!sentenceDate) {
    errors.push(
      err(
        [...loc, "sentence_date"],
        "Input should be a valid date",
        "date_type",
        obj.sentence_date,
      ),
    );
  }

  const age_at_offence = Number(obj.age_at_offence);
  const age_at_conviction = Number(obj.age_at_conviction);
  const age_at_sentence = Number(obj.age_at_sentence);

  if (
    !Number.isInteger(age_at_offence) || age_at_offence < 10 ||
    age_at_offence > 120
  ) {
    errors.push(
      err(
        [...loc, "age_at_offence"],
        "Input should be an integer between 10 and 120",
        "int_range",
        obj.age_at_offence,
      ),
    );
  }
  if (
    !Number.isInteger(age_at_conviction) || age_at_conviction < 10 ||
    age_at_conviction > 120
  ) {
    errors.push(
      err(
        [...loc, "age_at_conviction"],
        "Input should be an integer between 10 and 120",
        "int_range",
        obj.age_at_conviction,
      ),
    );
  }
  if (
    !Number.isInteger(age_at_sentence) || age_at_sentence < 10 ||
    age_at_sentence > 120
  ) {
    errors.push(
      err(
        [...loc, "age_at_sentence"],
        "Input should be an integer between 10 and 120",
        "int_range",
        obj.age_at_sentence,
      ),
    );
  }

  const plea_stage = obj.plea_stage;
  if (
    typeof plea_stage !== "string" ||
    !PLEA_STAGE_VALUES.has(plea_stage as PleaStage)
  ) {
    errors.push(
      err(
        [...loc, "plea_stage"],
        "Input should be a valid plea_stage",
        "literal_error",
        plea_stage,
      ),
    );
  }

  const sentence_type = obj.sentence_type;
  if (
    typeof sentence_type !== "string" ||
    !SENTENCE_TYPE_VALUES.has(sentence_type as SentenceType)
  ) {
    errors.push(
      err(
        [...loc, "sentence_type"],
        "Input should be a valid sentence_type",
        "literal_error",
        sentence_type,
      ),
    );
  }

  const numberOrNull = (
    field: string,
    min = -Infinity,
  ): number | null | undefined => {
    const v = obj[field];
    if (v == null) return null;
    if (typeof v !== "number" || Number.isNaN(v) || v < min) return undefined;
    return v;
  };

  const intOrDefault = (
    field: string,
    min = 0,
    dflt = 0,
  ): number | undefined => {
    const v = obj[field];
    if (v == null) return dflt;
    if (!Number.isInteger(v) || v < min) return undefined;
    return v;
  };

  const boolOrDefault = (field: string, dflt = false): boolean | undefined => {
    const v = obj[field];
    if (v == null) return dflt;
    if (typeof v !== "boolean") return undefined;
    return v;
  };

  const pre_plea_term_months = numberOrNull("pre_plea_term_months", 0);
  const extension_months = obj.extension_months == null
    ? 0
    : typeof obj.extension_months === "number" && obj.extension_months >= 0
    ? obj.extension_months
    : undefined;
  const fine_amount = numberOrNull("fine_amount", 0);

  if (pre_plea_term_months === undefined) {
    errors.push(
      err(
        [...loc, "pre_plea_term_months"],
        "Input should be a non-negative number",
        "float_range",
        obj.pre_plea_term_months,
      ),
    );
  }
  if (extension_months === undefined) {
    errors.push(
      err(
        [...loc, "extension_months"],
        "Input should be a non-negative number",
        "float_range",
        obj.extension_months,
      ),
    );
  }
  if (fine_amount === undefined) {
    errors.push(
      err(
        [...loc, "fine_amount"],
        "Input should be a non-negative number",
        "float_range",
        obj.fine_amount,
      ),
    );
  }

  const dangerousness_assessed = boolOrDefault("dangerousness_assessed", false);
  const prior_listed_offence_with_custody = boolOrDefault(
    "prior_listed_offence_with_custody",
    false,
  );
  const prior_domestic_burglary_count = intOrDefault(
    "prior_domestic_burglary_count",
    0,
    0,
  );
  const prior_class_a_trafficking_count = intOrDefault(
    "prior_class_a_trafficking_count",
    0,
    0,
  );
  const prior_relevant_weapon_conviction = boolOrDefault(
    "prior_relevant_weapon_conviction",
    false,
  );
  const terrorism_flag = boolOrDefault("terrorism_flag", false);
  const minimum_sentence_unjust_or_exceptional = boolOrDefault(
    "minimum_sentence_unjust_or_exceptional",
    false,
  );
  const replicate_ace_release_bug = boolOrDefault(
    "replicate_ace_release_bug",
    true,
  );

  const boolFields = [
    ["dangerousness_assessed", dangerousness_assessed],
    ["prior_listed_offence_with_custody", prior_listed_offence_with_custody],
    ["prior_relevant_weapon_conviction", prior_relevant_weapon_conviction],
    ["terrorism_flag", terrorism_flag],
    [
      "minimum_sentence_unjust_or_exceptional",
      minimum_sentence_unjust_or_exceptional,
    ],
    ["replicate_ace_release_bug", replicate_ace_release_bug],
  ] as const;

  for (const [name, parsed] of boolFields) {
    if (parsed === undefined) {
      errors.push(
        err(
          [...loc, name],
          "Input should be a valid boolean",
          "bool_type",
          obj[name],
        ),
      );
    }
  }

  if (prior_domestic_burglary_count === undefined) {
    errors.push(
      err(
        [...loc, "prior_domestic_burglary_count"],
        "Input should be a non-negative integer",
        "int_range",
        obj.prior_domestic_burglary_count,
      ),
    );
  }
  if (prior_class_a_trafficking_count === undefined) {
    errors.push(
      err(
        [...loc, "prior_class_a_trafficking_count"],
        "Input should be a non-negative integer",
        "int_range",
        obj.prior_class_a_trafficking_count,
      ),
    );
  }

  const culpability = obj.culpability == null
    ? null
    : typeof obj.culpability === "string"
    ? obj.culpability
    : undefined;
  const harm = obj.harm == null
    ? null
    : typeof obj.harm === "string"
    ? obj.harm
    : undefined;
  if (obj.culpability != null && culpability === undefined) {
    errors.push(
      err(
        [...loc, "culpability"],
        "Input should be a valid string",
        "string_type",
        obj.culpability,
      ),
    );
  }
  if (obj.harm != null && harm === undefined) {
    errors.push(
      err(
        [...loc, "harm"],
        "Input should be a valid string",
        "string_type",
        obj.harm,
      ),
    );
  }

  if (!offence_id && !offence_query) {
    errors.push(
      err(loc, "Provide either offence_id or offence_query", "value_error"),
    );
  }

  const parsed: CalculateSentenceRequest = {
    offence_id,
    offence_query,
    offence_date: obj.offence_date as string,
    conviction_date: obj.conviction_date as string,
    sentence_date: obj.sentence_date as string,
    age_at_offence,
    age_at_conviction,
    age_at_sentence,
    plea_stage: plea_stage as PleaStage,
    sentence_type: sentence_type as SentenceType,
    culpability: culpability ?? null,
    harm: harm ?? null,
    pre_plea_term_months: pre_plea_term_months ?? null,
    extension_months: extension_months ?? 0,
    fine_amount: fine_amount ?? null,
    dangerousness_assessed: dangerousness_assessed ?? false,
    prior_listed_offence_with_custody: prior_listed_offence_with_custody ??
      false,
    prior_domestic_burglary_count: prior_domestic_burglary_count ?? 0,
    prior_class_a_trafficking_count: prior_class_a_trafficking_count ?? 0,
    prior_relevant_weapon_conviction: prior_relevant_weapon_conviction ?? false,
    terrorism_flag: terrorism_flag ?? false,
    minimum_sentence_unjust_or_exceptional:
      minimum_sentence_unjust_or_exceptional ?? false,
    replicate_ace_release_bug: replicate_ace_release_bug ?? true,
  };

  return { errors, value: parsed };
}

function validateSearchGuidelinesRequest(
  value: unknown,
  loc: (string | number)[],
): { errors: ValidationItem[]; value: SearchGuidelinesRequest } {
  const base = ensureObject(value, loc);
  if (base.errors.length || !base.value) {
    return { errors: base.errors, value: {} as SearchGuidelinesRequest };
  }

  const obj = base.value;
  const allowed = new Set(["query", "offence_id", "top_k"]);
  const errors = forbidUnknownKeys(obj, allowed, loc);

  if (typeof obj.query !== "string" || !obj.query.trim()) {
    errors.push(
      err(
        [...loc, "query"],
        "Input should be a valid string",
        "string_type",
        obj.query,
      ),
    );
  }

  const offence_id = obj.offence_id == null
    ? null
    : typeof obj.offence_id === "string"
    ? obj.offence_id
    : undefined;
  if (obj.offence_id != null && offence_id === undefined) {
    errors.push(
      err(
        [...loc, "offence_id"],
        "Input should be a valid string",
        "string_type",
        obj.offence_id,
      ),
    );
  }

  let top_k = 6;
  if (obj.top_k != null) {
    if (!Number.isInteger(obj.top_k) || obj.top_k < 1 || obj.top_k > 20) {
      errors.push(
        err(
          [...loc, "top_k"],
          "Input should be an integer between 1 and 20",
          "int_range",
          obj.top_k,
        ),
      );
    } else {
      top_k = obj.top_k;
    }
  }

  return {
    errors,
    value: {
      query: typeof obj.query === "string" ? obj.query : "",
      offence_id: offence_id ?? null,
      top_k,
    },
  };
}

function validateChatTurnRequest(
  value: unknown,
  loc: (string | number)[],
): { errors: ValidationItem[]; value: ChatTurnRequest } {
  const base = ensureObject(value, loc);
  if (base.errors.length || !base.value) {
    return { errors: base.errors, value: {} as ChatTurnRequest };
  }

  const obj = base.value;
  const allowed = new Set([
    "message",
    "offence_id",
    "offence_query",
    "calculation",
    "top_k",
  ]);
  const errors = forbidUnknownKeys(obj, allowed, loc);

  if (typeof obj.message !== "string" || !obj.message.trim()) {
    errors.push(
      err(
        [...loc, "message"],
        "Input should be a valid string",
        "string_type",
        obj.message,
      ),
    );
  }

  const offence_id = obj.offence_id == null
    ? null
    : typeof obj.offence_id === "string"
    ? obj.offence_id
    : undefined;
  const offence_query = obj.offence_query == null
    ? null
    : typeof obj.offence_query === "string"
    ? obj.offence_query
    : undefined;

  if (obj.offence_id != null && offence_id === undefined) {
    errors.push(
      err(
        [...loc, "offence_id"],
        "Input should be a valid string",
        "string_type",
        obj.offence_id,
      ),
    );
  }
  if (obj.offence_query != null && offence_query === undefined) {
    errors.push(
      err(
        [...loc, "offence_query"],
        "Input should be a valid string",
        "string_type",
        obj.offence_query,
      ),
    );
  }

  let calculation: CalculateSentenceRequest | null = null;
  if (obj.calculation != null) {
    const calcParsed = validateCalculateSentenceRequest(obj.calculation, [
      ...loc,
      "calculation",
    ]);
    errors.push(...calcParsed.errors);
    calculation = calcParsed.value;
  }

  let top_k = 5;
  if (obj.top_k != null) {
    if (!Number.isInteger(obj.top_k) || obj.top_k < 1 || obj.top_k > 20) {
      errors.push(
        err(
          [...loc, "top_k"],
          "Input should be an integer between 1 and 20",
          "int_range",
          obj.top_k,
        ),
      );
    } else {
      top_k = obj.top_k;
    }
  }

  return {
    errors,
    value: {
      message: typeof obj.message === "string" ? obj.message : "",
      offence_id: offence_id ?? null,
      offence_query: offence_query ?? null,
      calculation,
      top_k,
    },
  };
}

async function calculateFromRequest(
  req: CalculateSentenceRequest,
): Promise<CalculateSentenceResponse> {
  const { offence, trace } = await resolveOffence(
    req.offence_id ?? null,
    req.offence_query ?? null,
  );
  const matrixRows = await fetchSentencingMatrix(offence.offence_id);

  const model: SentenceCalculationInput = {
    offence,
    offence_date: parseDateStrict(req.offence_date),
    conviction_date: parseDateStrict(req.conviction_date),
    sentence_date: parseDateStrict(req.sentence_date),
    age_at_offence: req.age_at_offence,
    age_at_conviction: req.age_at_conviction,
    age_at_sentence: req.age_at_sentence,
    plea_stage: req.plea_stage,
    sentence_type: req.sentence_type,
    culpability: req.culpability ?? null,
    harm: req.harm ?? null,
    pre_plea_term_months: req.pre_plea_term_months ?? null,
    extension_months: req.extension_months ?? 0,
    fine_amount: req.fine_amount ?? null,
    dangerousness_assessed: req.dangerousness_assessed ?? false,
    prior_listed_offence_with_custody: req.prior_listed_offence_with_custody ??
      false,
    prior_domestic_burglary_count: req.prior_domestic_burglary_count ?? 0,
    prior_class_a_trafficking_count: req.prior_class_a_trafficking_count ?? 0,
    prior_relevant_weapon_conviction: req.prior_relevant_weapon_conviction ??
      false,
    terrorism_flag: req.terrorism_flag ?? false,
    minimum_sentence_unjust_or_exceptional:
      req.minimum_sentence_unjust_or_exceptional ?? false,
    replicate_ace_release_bug: req.replicate_ace_release_bug ?? true,
  };

  const errors = validateInput(model);
  if (errors.length) {
    throw httpError(422, errors.join("; "));
  }

  const result = calculateSentence(model, matrixRows);
  result.trace = [...trace, ...result.trace];

  try {
    await supabase.rpc("api_store_calculation_audit", {
      p_offence_id: result.offence_id,
      p_request_payload: req,
      p_result_payload: result,
    });
  } catch {
    // Audit logging should not block API responses.
  }

  return result;
}

async function resolveOffence(
  offenceId: string | null,
  offenceQuery: string | null,
): Promise<{ offence: OffenceRecord; trace: string[] }> {
  const trace: string[] = [];

  if (offenceId) {
    const { data, error } = await supabase.rpc("api_fetch_offence_by_id", {
      p_offence_id: offenceId,
    });
    if (error) {
      throw httpError(error.code === "22P02" ? 422 : 500, error.message);
    }
    if (!data || data.length === 0) {
      throw httpError(404, `Offence not found: ${offenceId}`);
    }
    return { offence: toOffence(data[0]), trace };
  }

  if (!offenceQuery) {
    throw httpError(400, "Provide offence_id or offence_query");
  }

  const { data, error } = await supabase.rpc("api_search_offences", {
    p_query: offenceQuery,
    p_limit: 5,
  });
  if (error) {
    throw httpError(500, error.message);
  }
  if (!data || data.length === 0) {
    throw httpError(404, `No offence found for query: ${offenceQuery}`);
  }

  const chosen = toOffence(data[0]);
  trace.push(
    `Resolved offence query '${offenceQuery}' to '${chosen.canonical_name}' (${chosen.offence_id}).`,
  );
  if (data.length > 1) {
    trace.push(
      "Multiple matches found; top similarity match selected automatically.",
    );
  }

  return { offence: chosen, trace };
}

function toOffence(row: Record<string, unknown>): OffenceRecord {
  return {
    offence_id: String(row.offence_id ?? ""),
    canonical_name: String(row.canonical_name ?? ""),
    short_name: String(row.short_name ?? ""),
    offence_category: String(row.offence_category ?? ""),
    provision: String(row.provision ?? ""),
    guideline_url: String(row.guideline_url ?? ""),
    legislation_url: String(row.legislation_url ?? ""),
    maximum_sentence_type: String(row.maximum_sentence_type ?? ""),
    maximum_sentence_amount: String(row.maximum_sentence_amount ?? ""),
    minimum_sentence_code: String(row.minimum_sentence_code ?? ""),
    specified_violent: Boolean(row.specified_violent),
    specified_sexual: Boolean(row.specified_sexual),
    specified_terrorist: Boolean(row.specified_terrorist),
    listed_offence: Boolean(row.listed_offence),
    schedule18a_offence: Boolean(row.schedule18a_offence),
    schedule19za: Boolean(row.schedule19za),
    cta_notification: Boolean(row.cta_notification),
  };
}

async function fetchSentencingMatrix(
  offenceId: string,
): Promise<Record<string, unknown>[]> {
  const { data, error } = await supabase.rpc("api_fetch_sentencing_matrix", {
    p_offence_id: offenceId,
  });
  if (error) {
    throw httpError(500, error.message);
  }
  return (data as Record<string, unknown>[] | null) ?? [];
}

async function searchGuidelines(
  query: string,
  offenceId: string | null,
  topK?: number,
): Promise<Record<string, unknown>[]> {
  const k = topK ?? ENV.retrievalTopK;

  if (ENV.enableVectorSearch && ENV.openaiApiKey) {
    const embedding = await embed(query);
    if (embedding) {
      const { data, error } = await supabase.rpc(
        "api_search_guideline_chunks_hybrid",
        {
          p_query: query,
          p_query_embedding: embedding,
          p_top_k: k,
          p_offence_id: offenceId,
        },
      );
      if (error) {
        throw httpError(500, error.message);
      }
      return (data as Record<string, unknown>[] | null) ?? [];
    }
  }

  const { data, error } = await supabase.rpc(
    "api_search_guideline_chunks_text",
    {
      p_query: query,
      p_top_k: k,
      p_offence_id: offenceId,
    },
  );
  if (error) {
    throw httpError(500, error.message);
  }
  return (data as Record<string, unknown>[] | null) ?? [];
}

async function embed(query: string): Promise<number[] | null> {
  const response = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${ENV.openaiApiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: ENV.openaiEmbeddingModel,
      input: [query],
    }),
  });

  if (!response.ok) {
    return null;
  }

  const payload = await response.json();
  const embedding = payload?.data?.[0]?.embedding;
  if (!Array.isArray(embedding)) {
    return null;
  }
  return embedding as number[];
}

function convertChunks(rows: Record<string, unknown>[]): GuidelineChunkOut[] {
  return rows.map((row) => ({
    chunk_id: String(row.chunk_id ?? ""),
    guideline_id: String(row.guideline_id ?? ""),
    offence_id: row.offence_id == null ? null : String(row.offence_id),
    section_type: row.section_type == null ? null : String(row.section_type),
    section_heading: row.section_heading == null
      ? null
      : String(row.section_heading),
    chunk_text: String(row.chunk_text ?? ""),
    source_url: row.source_url == null ? null : String(row.source_url),
    score: typeof row.score === "number"
      ? row.score
      : row.score == null
      ? null
      : Number(row.score),
  }));
}

function parseDateStrict(value: string): Date {
  const d = parseDate(value);
  if (!d) {
    throw httpError(422, `Invalid date: ${value}`);
  }
  return d;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function validateInput(data: SentenceCalculationInput): string[] {
  const errors: string[] = [];

  if (data.offence_date > data.conviction_date) {
    errors.push("offence_date must be on or before conviction_date");
  }
  if (data.conviction_date > data.sentence_date) {
    errors.push("conviction_date must be on or before sentence_date");
  }

  if (data.age_at_offence < 10 || data.age_at_offence > 120) {
    errors.push("age_at_offence must be between 10 and 120");
  }
  if (data.age_at_conviction < data.age_at_offence) {
    errors.push("age_at_conviction must be >= age_at_offence");
  }
  if (data.age_at_sentence < data.age_at_conviction) {
    errors.push("age_at_sentence must be >= age_at_conviction");
  }

  if (data.pre_plea_term_months !== null && data.pre_plea_term_months < 0) {
    errors.push("pre_plea_term_months must be non-negative");
  }
  if (data.extension_months < 0) {
    errors.push("extension_months must be non-negative");
  }
  if (data.fine_amount !== null && data.fine_amount < 0) {
    errors.push("fine_amount must be non-negative");
  }

  return errors;
}

function isCustodial(sentenceType: SentenceType): boolean {
  return CUSTODIAL_SENTENCE_TYPES.has(sentenceType);
}

function hasLifeMaximum(offence: OffenceRecord): boolean {
  return offence.maximum_sentence_amount.toLowerCase().includes("life");
}

function pleaFactor(stage: PleaStage): number {
  return PLEA_FACTORS[stage] ?? 1;
}

function sentenceAfterPlea(
  prePleaTermMonths: number | null,
  stage: PleaStage,
): number | null {
  if (prePleaTermMonths === null) {
    return null;
  }
  return round2(prePleaTermMonths * pleaFactor(stage));
}

function minimumSentenceDecision(
  data: SentenceCalculationInput,
): MinimumSentenceDecision {
  if (data.minimum_sentence_unjust_or_exceptional) {
    return {
      triggered: false,
      floor_pre_months: null,
      floor_post_months: null,
      reason: "minimum disapplied by input override",
    };
  }

  const code = data.offence.minimum_sentence_code.trim().toUpperCase();
  if (!code) {
    return {
      triggered: false,
      floor_pre_months: null,
      floor_post_months: null,
      reason: null,
    };
  }

  const adult = data.age_at_sentence >= 18;
  const youth1617 = data.age_at_sentence >= 16 && data.age_at_sentence <= 17;
  const guilty = data.plea_stage !== "not_guilty";

  if (code === "A") {
    if (adult && data.prior_domestic_burglary_count >= 2) {
      return {
        triggered: true,
        floor_pre_months: 36,
        floor_post_months: guilty ? 28.8 : 36,
        reason: "Domestic burglary minimum",
      };
    }
    return {
      triggered: false,
      floor_pre_months: null,
      floor_post_months: null,
      reason: "Conditions for A not met",
    };
  }

  if (code === "B") {
    if (
      adult && data.offence_date >= new Date("1997-10-01T00:00:00Z") &&
      data.prior_class_a_trafficking_count >= 2
    ) {
      return {
        triggered: true,
        floor_pre_months: 84,
        floor_post_months: guilty ? 67.2 : 84,
        reason: "Class A trafficking minimum",
      };
    }
    return {
      triggered: false,
      floor_pre_months: null,
      floor_post_months: null,
      reason: "Conditions for B not met",
    };
  }

  if (["C1", "C2", "C3", "C4"].includes(code)) {
    const starts: Record<string, Date> = {
      C1: new Date("2004-01-22T00:00:00Z"),
      C2: new Date("2007-04-06T00:00:00Z"),
      C3: new Date("2014-07-14T00:00:00Z"),
      C4: new Date("1900-01-01T00:00:00Z"),
    };

    if (data.offence_date < starts[code]) {
      return {
        triggered: false,
        floor_pre_months: null,
        floor_post_months: null,
        reason: "Firearms date threshold not met",
      };
    }

    if (adult) {
      return {
        triggered: true,
        floor_pre_months: 60,
        floor_post_months: 60,
        reason: "Firearms adult minimum",
      };
    }

    if (youth1617) {
      return {
        triggered: true,
        floor_pre_months: 36,
        floor_post_months: 36,
        reason: "Firearms youth minimum",
      };
    }

    return {
      triggered: false,
      floor_pre_months: null,
      floor_post_months: null,
      reason: "Under 16",
    };
  }

  if (code === "D") {
    if (data.offence_date < new Date("2015-07-17T00:00:00Z")) {
      return {
        triggered: false,
        floor_pre_months: null,
        floor_post_months: null,
        reason: "Weapon possession date threshold not met",
      };
    }

    if (data.age_at_offence < 16) {
      return {
        triggered: false,
        floor_pre_months: null,
        floor_post_months: null,
        reason: "Under 16 at offence",
      };
    }

    if (!data.prior_relevant_weapon_conviction) {
      return {
        triggered: false,
        floor_pre_months: null,
        floor_post_months: null,
        reason: "No qualifying prior conviction",
      };
    }

    if (data.age_at_conviction >= 18) {
      return {
        triggered: true,
        floor_pre_months: 6,
        floor_post_months: guilty ? 4.8 : 6,
        reason: "Weapon possession adult minimum",
      };
    }

    if (data.age_at_conviction >= 16 && data.age_at_conviction <= 17) {
      return {
        triggered: true,
        floor_pre_months: 4,
        floor_post_months: null,
        reason: "Weapon possession youth DTO minimum",
      };
    }

    return {
      triggered: false,
      floor_pre_months: null,
      floor_post_months: null,
      reason: "Under 16 at conviction",
    };
  }

  if (code === "E") {
    if (adult) {
      return {
        triggered: true,
        floor_pre_months: 6,
        floor_post_months: guilty ? 4.8 : 6,
        reason: "Threats with weapon adult minimum",
      };
    }

    if (youth1617) {
      return {
        triggered: true,
        floor_pre_months: 4,
        floor_post_months: null,
        reason: "Threats with weapon youth DTO minimum",
      };
    }

    return {
      triggered: false,
      floor_pre_months: null,
      floor_post_months: null,
      reason: "Under 16",
    };
  }

  return {
    triggered: false,
    floor_pre_months: null,
    floor_post_months: null,
    reason: `Unsupported minimum code ${code}`,
  };
}

function applyMinimumSentenceFloor(
  prePleaTermMonths: number | null,
  postPleaTermMonths: number | null,
  decision: MinimumSentenceDecision,
): { pre: number | null; post: number | null; trace: string[] } {
  const trace: string[] = [];
  if (!decision.triggered) {
    return { pre: prePleaTermMonths, post: postPleaTermMonths, trace };
  }

  let pre = prePleaTermMonths;
  let post = postPleaTermMonths;

  if (decision.floor_pre_months !== null) {
    if (pre === null) {
      pre = decision.floor_pre_months;
      trace.push(
        `Pre-plea term set to minimum floor ${decision.floor_pre_months} months`,
      );
    } else if (pre < decision.floor_pre_months) {
      trace.push(
        `Pre-plea term raised from ${pre} to minimum floor ${decision.floor_pre_months} months`,
      );
      pre = decision.floor_pre_months;
    }
  }

  if (decision.floor_post_months !== null) {
    if (post === null) {
      post = decision.floor_post_months;
      trace.push(
        `Post-plea term set to minimum floor ${decision.floor_post_months} months`,
      );
    } else if (post < decision.floor_post_months) {
      trace.push(
        `Post-plea term raised from ${post} to minimum floor ${decision.floor_post_months} months`,
      );
      post = decision.floor_post_months;
    }
  }

  return { pre, post, trace };
}

function isFortyPercentRegime(
  offence: OffenceRecord,
  termMonths: number,
): boolean {
  if (termMonths > 48 && offence.specified_violent) {
    return false;
  }

  if (offence.offence_category.toLowerCase().includes("sexual offence")) {
    return false;
  }

  const provision = offence.provision.toLowerCase();
  if (
    provision.includes("protection from harassment") &&
    provision.includes("stalking")
  ) {
    return false;
  }

  for (const marker of FORTY_PERCENT_EXCLUSIONS) {
    if (provision.includes(marker)) {
      return false;
    }
  }

  return true;
}

function releaseDecision(
  data: SentenceCalculationInput,
  postPleaTermMonths: number | null,
): ReleaseDecision {
  const sentenceType = data.sentence_type;
  const offence = data.offence;

  if (
    sentenceType === "mandatory_life_sentence" ||
    sentenceType === "discretionary_life_sentence"
  ) {
    return {
      release_fraction: null,
      reason: "Life sentence: release not represented as determinate fraction",
    };
  }

  if (
    sentenceType === "community_order" ||
    sentenceType === "youth_rehabilitation_order" ||
    sentenceType === "fine" ||
    sentenceType === "conditional_discharge"
  ) {
    return { release_fraction: null, reason: "Non-custodial sentence" };
  }

  if (sentenceType === "suspended_sentence_order") {
    return {
      release_fraction: null,
      reason: "Suspended sentence: no immediate custody term",
    };
  }

  if (postPleaTermMonths === null) {
    return { release_fraction: null, reason: "No custodial term provided" };
  }

  if (
    sentenceType === "extended_sentence" ||
    sentenceType === "special_custodial_sentence"
  ) {
    return {
      release_fraction: 2 / 3,
      reason: "Extended/special custodial release at two-thirds",
    };
  }

  if (!isCustodial(sentenceType)) {
    return {
      release_fraction: null,
      reason: "Sentence type not treated as custodial",
    };
  }

  const term = postPleaTermMonths;
  const lifeMax = hasLifeMaximum(offence);

  if (
    term >= 84 && lifeMax &&
    (offence.specified_sexual || offence.specified_violent)
  ) {
    return {
      release_fraction: 2 / 3,
      reason: "Term >= 84m + life max + specified offence",
    };
  }

  if (offence.schedule19za || data.terrorism_flag) {
    return {
      release_fraction: 2 / 3,
      reason: "Schedule 19ZA / terrorism route",
    };
  }

  const provisionOrName = `${offence.provision} ${offence.canonical_name}`
    .toLowerCase();
  if (term >= 48) {
    if (lifeMax && offence.specified_sexual) {
      return {
        release_fraction: 2 / 3,
        reason: "Sexual offence with life max and term >= 48m",
      };
    }
    if (
      SERIOUS_PROVISION_MARKERS.some((marker) =>
        provisionOrName.includes(marker)
      )
    ) {
      return {
        release_fraction: 2 / 3,
        reason: "Specified serious offence marker with term >= 48m",
      };
    }
  }

  const fortyPercent = isFortyPercentRegime(offence, term);
  if (data.replicate_ace_release_bug) {
    if (fortyPercent) {
      return {
        release_fraction: 0.5,
        reason:
          "Replicating sentenceACE inconsistency for forty-percent regime",
      };
    }
    return {
      release_fraction: 0.4,
      reason:
        "Replicating sentenceACE inconsistency for non-forty-percent regime",
    };
  }

  if (fortyPercent) {
    return { release_fraction: 0.4, reason: "Forty-percent regime" };
  }

  return { release_fraction: 0.5, reason: "Halfway release regime" };
}

function victimSurcharge(
  offenceDate: Date,
  ageAtOffence: number,
  sentenceType: SentenceType,
  fineAmount: number | null,
  custodialTermMonths: number | null,
): number {
  const adult = ageAtOffence >= 18;

  if (offenceDate < new Date("2012-10-01T00:00:00Z")) {
    return 0;
  }

  let adultBand: number[];
  let youthBand: number[];
  let finePct: number;

  if (offenceDate >= new Date("2022-06-16T00:00:00Z")) {
    adultBand = [26, 0, 2000, 114, 154, 187, 154, 187, 228];
    youthBand = [20, 26, 41];
    finePct = 0.4;
  } else if (offenceDate >= new Date("2020-04-14T00:00:00Z")) {
    adultBand = [22, 34, 190, 95, 128, 156, 128, 156, 190];
    youthBand = [17, 22, 34];
    finePct = 0.1;
  } else if (offenceDate >= new Date("2019-06-28T00:00:00Z")) {
    adultBand = [21, 32, 181, 90, 122, 149, 122, 149, 181];
    youthBand = [16, 21, 32];
    finePct = 0.1;
  } else if (offenceDate >= new Date("2016-04-08T00:00:00Z")) {
    adultBand = [20, 30, 170, 85, 115, 140, 115, 140, 170];
    youthBand = [15, 20, 30];
    finePct = 0.1;
  } else {
    adultBand = [15, 20, 120, 60, 80, 100, 80, 100, 120];
    youthBand = [10, 15, 20];
    finePct = 0.1;
  }

  if (!adult) {
    if (sentenceType === "conditional_discharge") return youthBand[0];
    if (
      sentenceType === "fine" ||
      sentenceType === "youth_rehabilitation_order" ||
      sentenceType === "community_order"
    ) return youthBand[1];
    if (
      CUSTODIAL_SENTENCE_TYPES.has(sentenceType) ||
      sentenceType === "suspended_sentence_order"
    ) return youthBand[2];
    return 0;
  }

  if (sentenceType === "conditional_discharge") {
    return adultBand[0];
  }

  if (sentenceType === "fine") {
    if (fineAmount === null) return 0;
    if (finePct === 0.4) {
      return Math.min(adultBand[2], Math.round(fineAmount * finePct));
    }
    const amount = Math.round(fineAmount * finePct);
    return Math.min(adultBand[2], Math.max(adultBand[1], amount));
  }

  if (
    sentenceType === "community_order" ||
    sentenceType === "youth_rehabilitation_order"
  ) {
    return adultBand[3];
  }

  if (sentenceType === "suspended_sentence_order") {
    const months = custodialTermMonths ?? 0;
    return months <= 6 ? adultBand[4] : adultBand[5];
  }

  if (CUSTODIAL_SENTENCE_TYPES.has(sentenceType)) {
    const months = custodialTermMonths ?? 0;
    if (months <= 6) return adultBand[6];
    if (months <= 24) return adultBand[7];
    return adultBand[8];
  }

  return 0;
}

function pickSentencingRange(
  culpability: string | null,
  harm: string | null,
  matrixRows: Record<string, unknown>[],
): SentencingRangeOut | null {
  if (!culpability || !harm) return null;

  const desiredCulp = culpability.trim().toLowerCase();
  const desiredHarm = harm.trim().toLowerCase();

  for (const row of matrixRows) {
    const rowCulp = String(row.culpability ?? "").trim().toLowerCase();
    const rowHarm = String(row.harm ?? "").trim().toLowerCase();
    if (rowCulp === desiredCulp && rowHarm === desiredHarm) {
      return {
        culpability: String(row.culpability ?? ""),
        harm: String(row.harm ?? ""),
        starting_point_text: String(row.starting_point_text ?? ""),
        category_range_text: String(row.category_range_text ?? ""),
      };
    }
  }

  for (const row of matrixRows) {
    const rowCulp = String(row.culpability ?? "").trim().toLowerCase();
    const rowHarm = String(row.harm ?? "").trim().toLowerCase();
    if (rowCulp.includes(desiredCulp) && rowHarm.includes(desiredHarm)) {
      return {
        culpability: String(row.culpability ?? ""),
        harm: String(row.harm ?? ""),
        starting_point_text: String(row.starting_point_text ?? ""),
        category_range_text: String(row.category_range_text ?? ""),
      };
    }
  }

  return null;
}

function buildWarnings(
  data: SentenceCalculationInput,
  prePleaTermMonths: number | null,
): string[] {
  const warnings: string[] = [];
  const offence = data.offence;

  if (
    offence.listed_offence && data.age_at_sentence >= 18 &&
    data.prior_listed_offence_with_custody && (prePleaTermMonths ?? 0) >= 120
  ) {
    warnings.push(
      "Mandatory life sentence route may be engaged for repeat listed offence; review SC283/SC273 conditions.",
    );
  }

  if (
    (offence.specified_violent || offence.specified_sexual ||
      offence.specified_terrorist) &&
    data.dangerousness_assessed && hasLifeMaximum(offence)
  ) {
    warnings.push(
      "Dangerousness + specified offence + life max may trigger mandatory life provisions; review SC285/SC274/SC258.",
    );
  }

  if (
    data.sentence_type === "special_custodial_sentence" &&
    !offence.schedule18a_offence
  ) {
    warnings.push(
      "Special custodial sentence selected but offence is not marked Schedule 18A in offence metadata.",
    );
  }

  return warnings;
}

function calculateSentence(
  data: SentenceCalculationInput,
  matrixRows: Record<string, unknown>[],
): CalculateSentenceResponse {
  const trace: string[] = [];

  let prePlea = data.pre_plea_term_months;
  let postPlea = sentenceAfterPlea(prePlea, data.plea_stage);

  if (prePlea !== null) {
    trace.push(
      `Applied plea factor for ${data.plea_stage}: pre=${prePlea} -> post=${postPlea}`,
    );
  }

  const minDecision = minimumSentenceDecision(data);
  if (minDecision.triggered) {
    trace.push(minDecision.reason ?? "Minimum sentence rule triggered");
  }

  const floored = applyMinimumSentenceFloor(prePlea, postPlea, minDecision);
  prePlea = floored.pre;
  postPlea = floored.post;
  trace.push(...floored.trace);

  const release = releaseDecision(data, postPlea);
  trace.push(release.reason);

  let estimatedTime: number | null = null;
  if (postPlea !== null && release.release_fraction !== null) {
    estimatedTime = round2(postPlea * release.release_fraction);
  }

  const surcharge = victimSurcharge(
    data.offence_date,
    data.age_at_offence,
    data.sentence_type,
    data.fine_amount,
    postPlea,
  );
  const matchedRange = pickSentencingRange(
    data.culpability,
    data.harm,
    matrixRows,
  );
  const warnings = buildWarnings(data, prePlea);

  return {
    offence_id: data.offence.offence_id,
    offence_name: data.offence.canonical_name,
    sentence_type: data.sentence_type,
    pre_plea_term_months: prePlea,
    post_plea_term_months: postPlea,
    minimum_sentence_triggered: minDecision.triggered,
    minimum_floor_pre_plea_months: minDecision.floor_pre_months,
    minimum_floor_post_plea_months: minDecision.floor_post_months,
    release_fraction: release.release_fraction,
    estimated_time_in_custody_months: estimatedTime,
    victim_surcharge_gbp: round2(surcharge),
    matched_range: matchedRange,
    warnings,
    trace,
  };
}
