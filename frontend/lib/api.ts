export type Me = {
  id: string;
  email: string;
  display_name: string;
  email_verified: boolean;
  roles: string[];
  permissions: string[];
  plan_code: string;
  csrf_token: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fieldErrors: { field: string; message: string }[] = [],
  ) {
    super(message);
  }
}

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|; )justice_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken();
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, "We couldn't reach the server. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(res.status, data?.detail ?? `Request failed (${res.status})`, data?.errors ?? []);
  }
  return data as T;
}

export const MATTER_LABELS: Record<string, string> = {
  constitutional: "Constitutional & fundamental rights",
  criminal: "Criminal law & procedure",
  police_procedure: "Police, arrest, detention & bail",
  civil: "Civil disputes",
  family: "Family, marriage, divorce & inheritance",
  property_tenancy: "Property, land & tenancy",
  employment: "Employment & workplace",
  consumer: "Consumer protection",
  cyber_privacy: "Cybercrime, fraud & privacy",
  business_contracts: "Business, contracts & companies",
  banking_finance: "Banking, loans & debt",
  motor_accident_insurance: "Motor accidents & insurance",
  education: "Education & student grievances",
  women_child_protection: "Women's rights, child protection & domestic violence",
  disability: "Disability rights",
  environment: "Environmental rights",
  intellectual_property: "Intellectual property",
  administrative: "Government services & administrative law",
  immigration: "Immigration & nationality",
  adr_legal_aid: "Legal aid, mediation & arbitration",
};

export const STAGE_LABELS: Record<string, string> = {
  not_started: "Not started",
  notice_sent: "Notice sent",
  notice_received: "Notice received",
  negotiation: "Negotiation",
  complaint_filed: "Complaint filed",
  case_pending: "Case pending",
  order_passed: "Order passed",
  appeal: "Appeal",
  closed: "Closed",
};

/** Multipart upload (e.g. official source documents). Same error handling and CSRF header as api(). */
export async function apiForm<T = unknown>(path: string, form: FormData): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { method: "POST", body: form, credentials: "same-origin", headers: { "X-CSRF-Token": csrfToken() } });
  } catch {
    throw new ApiError(0, "We couldn't reach the server. Check your connection and try again.");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? `Upload failed (${res.status})`, data?.errors ?? []);
  return data as T;
}
