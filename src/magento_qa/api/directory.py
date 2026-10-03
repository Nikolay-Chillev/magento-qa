"""Countries and regions (anonymous REST API)."""

from magento_qa.api.errors import raise_for_magento_error
from magento_qa.api.http import HttpClient
from magento_qa.models.directory import Country


class DirectoryClient:
    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def country(self, country_id: str) -> Country:
        response = self.http.get(f"rest/V1/directory/countries/{country_id}")
        raise_for_magento_error(response)
        return Country.model_validate(response.json())

    def region_ids(self, country_id: str) -> dict[str, int]:
        """Map ISO 3166-2 region codes (e.g. ``BG-22``) to Magento region ids."""
        return {region.code: region.id for region in self.country(country_id).available_regions}
