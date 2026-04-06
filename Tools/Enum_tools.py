import os
from dotenv import load_dotenv
from langchain.tools import tool
import requests


load_dotenv(dotenv_path='.env', override=True)

vulners_api = os.getenv("VULNERS_API_KEY")
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

@tool
def nvd_lookup(service_and_version: str) -> str:
    """
    Queries the NVD (National Vulnerability Database) for CVEs matching
    a given service name and optional version string.

    Args:
        service_and_version: Service and version to search for.
    """
    try:

        parts = service_and_version.strip().split(" ", 1)
        service = parts[0]
        version = parts[1] if len(parts) > 1 else ""

        keyword = f"{service} {version}".strip()

        params = {
            "keywordSearch": keyword,
            "resultsPerPage": 10,
            "startIndex": 0,
        }

        response = requests.get(NVD_API, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        total = data.get("totalResults", 0)
        vulns = data.get("vulnerabilities", [])

        if not vulns:
            return f"No CVEs found for '{keyword}'."

        results = [f"CVEs for '{keyword}' ({total} total, showing top {len(vulns)}):"]
        results.append("=" * 60)

        for item in vulns:
            cve = item.get("cve", {})
            cve_id = cve.get("id", "N/A")

            # Description
            descs = cve.get("descriptions", [])
            description = next(
                (d["value"] for d in descs if d.get("lang") == "en"),
                "No description available."
            )

            # CVSS score
            score = "N/A"
            severity = "N/A"
            metrics = cve.get("metrics", {})
            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                if key in metrics and metrics[key]:
                    cvss_data = metrics[key][0].get("cvssData", {})
                    score = cvss_data.get("baseScore", "N/A")
                    severity = cvss_data.get("baseSeverity", metrics[key][0].get("baseSeverity", "N/A"))
                    break

            # Published date
            published = cve.get("published", "N/A")[:10]

            # References
            refs = cve.get("references", [])
            ref_urls = [r["url"] for r in refs[:2]]

            results.append(f"\n[{cve_id}]  Score: {score} ({severity})  Published: {published}")
            results.append(f"  {description[:200]}{'...' if len(description) > 200 else ''}")
            if ref_urls:
                results.append(f"  Refs: {' | '.join(ref_urls)}")

        return "\n".join(results)
    
    except Exception as e:
        return(f'Error: {e}')