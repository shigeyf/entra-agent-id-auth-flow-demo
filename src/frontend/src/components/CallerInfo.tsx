import React from "react";

interface CallerInfoProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any | null;
  loading: boolean;
  error: string | null;
}

const CallerInfo: React.FC<CallerInfoProps> = ({ data, loading, error }) => {
  if (loading) {
    return <div className="caller-info loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="caller-info error">エラー: {error}</div>;
  }

  if (!data) {
    return null;
  }

  const { caller, humanReadable, resource, accessedAt } = data;

  return (
    <div className="caller-info">
      <h3>リソース API レスポンス</h3>

      <div className="summary">
        <p className="human-readable">{humanReadable}</p>
      </div>

      <table>
        <tbody>
          <tr>
            <th>Resource</th>
            <td>{resource}</td>
          </tr>
          <tr>
            <th>Accessed At</th>
            <td>{accessedAt}</td>
          </tr>
          <tr>
            <th>Caller Type</th>
            <td>
              <code>{caller.callerType}</code>
            </td>
          </tr>
          <tr>
            <th>Token Kind</th>
            <td>
              <code>{caller.tokenKind}</code>
            </td>
          </tr>
          <tr>
            <th>OID</th>
            <td>
              <code>{caller.oid}</code>
            </td>
          </tr>
          <tr>
            <th>UPN</th>
            <td>{caller.upn || "—"}</td>
          </tr>
          <tr>
            <th>Display Name</th>
            <td>{caller.displayName || "—"}</td>
          </tr>
          <tr>
            <th>App ID</th>
            <td>
              <code>{caller.appId || "—"}</code>
            </td>
          </tr>
          <tr>
            <th>Scopes</th>
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
            <th>Roles</th>
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
        <summary>生 JSON レスポンス</summary>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </details>
    </div>
  );
};

export default CallerInfo;
