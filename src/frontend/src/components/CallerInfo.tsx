import React from "react";
import { useTranslation } from "react-i18next";

const knownAppIds: Record<string, string> = Object.fromEntries(
  [
    [import.meta.env.ENTRA_SPA_APP_CLIENT_ID, "SPA Client"],
    [import.meta.env.ENTRA_RESOURCE_API_CLIENT_ID, "Identity Echo API"],
    [import.meta.env.ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID, "Agent Blueprint Identity"],
    [import.meta.env.ENTRA_AGENT_IDENTITY_CLIENT_ID, "Agent Identity"],
  ].filter(([id]) => id)
);

function resolveAppLabel(appId: string | undefined): string | null {
  if (!appId) return null;
  return knownAppIds[appId] ?? null;
}

interface CallerInfoProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any | null;
  loading: boolean;
  error: string | null;
}

const CallerInfo: React.FC<CallerInfoProps> = ({ data, loading, error }) => {
  const { t } = useTranslation();

  if (loading) {
    return <div className="caller-info loading">{t("callerInfo.loading")}</div>;
  }

  if (error) {
    return <div className="caller-info error">{t("callerInfo.errorPrefix")} {error}</div>;
  }

  if (!data) {
    return null;
  }

  const { caller, resource, accessedAt } = data;

  if (!caller) {
    return (
      <div className="caller-info error">
        {t("callerInfo.noCallerInfo")}
      </div>
    );
  }

  const callerDisplay = caller.upn || caller.displayName || caller.oid;
  const localizedSummary =
    caller.tokenKind === "delegated"
      ? t("callerInfo.summaryDelegated", {
          caller: callerDisplay,
          scopes: caller.scopes?.length > 0 ? caller.scopes.join(", ") : t("callerInfo.none"),
        })
      : t("callerInfo.summaryAppOnly", {
          roles: caller.roles?.length > 0 ? caller.roles.join(", ") : t("callerInfo.none"),
          oid: caller.oid,
        });

  return (
    <div className="caller-info">
      <h3>{t("callerInfo.heading")}</h3>

      <div className="summary">
        <p className="human-readable">{localizedSummary}</p>
      </div>

      <table>
        <tbody>
          <tr>
            <th>{t("callerInfo.resource")}</th>
            <td>{resource}</td>
          </tr>
          <tr>
            <th>{t("callerInfo.accessedAt")}</th>
            <td>{accessedAt}</td>
          </tr>
          <tr>
            <th>{t("callerInfo.tokenKind")}</th>
            <td>
              <code>{caller.tokenKind}</code>
            </td>
          </tr>
          <tr>
            <th>{t("callerInfo.oid")}</th>
            <td>
              <code>{caller.oid}</code>
            </td>
          </tr>
          <tr>
            <th>{t("callerInfo.upn")}</th>
            <td>{caller.upn || "—"}</td>
          </tr>
          <tr>
            <th>{t("callerInfo.displayName")}</th>
            <td>{caller.displayName || "—"}</td>
          </tr>
          <tr>
            <th>{t("callerInfo.appId")}</th>
            <td>
              <code>{caller.appId || "—"}</code>
              {resolveAppLabel(caller.appId) && (
                <span style={{ marginLeft: 8, opacity: 0.7 }}>
                  ({resolveAppLabel(caller.appId)})
                </span>
              )}
            </td>
          </tr>
          <tr>
            <th>{t("callerInfo.scopes")}</th>
            <td>
              {caller.scopes?.length > 0
                ? caller.scopes.map((s: string) => (
                    <code key={s} style={{ marginRight: 4 }}>
                      {s}
                    </code>
                  ))
                : "—"}
            </td>
          </tr>
          <tr>
            <th>{t("callerInfo.roles")}</th>
            <td>
              {caller.roles?.length > 0
                ? caller.roles.map((r: string) => (
                    <code key={r} style={{ marginRight: 4 }}>
                      {r}
                    </code>
                  ))
                : "—"}
            </td>
          </tr>
        </tbody>
      </table>

      <details>
        <summary>{t("callerInfo.rawJson")}</summary>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </details>
    </div>
  );
};

export default CallerInfo;
