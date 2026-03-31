const resourceApiUrl =
  import.meta.env.VITE_RESOURCE_API_URL ?? "http://localhost:8000";

export async function getCallerInfo(accessToken: string) {
  const response = await fetch(`${resourceApiUrl}/api/resource`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `API request failed: ${response.status} ${response.statusText} - ${errorText}`,
    );
  }

  return response.json();
}
