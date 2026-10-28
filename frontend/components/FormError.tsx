import { ApiError } from "@/lib/api";

export function FormError({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error instanceof ApiError ? error : null;
  return (
    <div className="alert alert-error" role="alert">
      <p>{e ? e.message : "Something went wrong."}</p>
      {e && e.fieldErrors.length > 0 && (
        <ul>
          {e.fieldErrors.map((f, i) => (
            <li key={i}>
              <strong>{f.field.replaceAll("_", " ")}</strong>: {f.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
