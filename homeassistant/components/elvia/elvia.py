"""elvia communication."""
from __future__ import annotations

#  import asyncio
import urllib.error
import urllib.parse
import urllib.request

import aiohttp
from pykson import Pykson

from .elvia_schema import MaxHours, MeterValues


class ElviaWebResponse:
    """Data class to wrap api response."""

    json: str
    status_code: int = 0  # Http status code

    def __init__(self, status_code: int, json: str) -> None:
        """Class init. Returns nothing."""
        self.json = json
        self.status_code = status_code


class ElviaData:
    """Data class for wrapping deserialized result."""

    status_code: int = 404
    data: MaxHours | MeterValues | None = None

    def __init__(self, status_code: int, data: MaxHours | MeterValues | None) -> None:
        """Class init. Returns nothing."""
        self.status_code = status_code
        self.data = data


class Elvia:
    """Communication class for elvia."""

    domain = "elvia.azure-api.net"
    jwt: str

    def __init__(self, jwt: str) -> None:
        """Class init. Returns nothing."""
        self.jwt = jwt

    # pylint: disable=invalid-name,broad-except,no-member
    async def request_elvia_for_response(self, path) -> ElviaWebResponse:
        """Return WebResponse data from elvia."""

        headers = {"Authorization": "Bearer %s" % self.jwt}

        async with aiohttp.ClientSession(headers=headers) as session:
            url = "https://" + self.domain + path
            async with session.get(url) as response:
                payload = await response.read()
                json_string = str(payload, "utf-8")
                elvia_response: ElviaWebResponse = ElviaWebResponse(
                    response.status, json_string
                )
                return elvia_response

    #        try:
    #            conn = http.client.HTTPSConnection("elvia.azure-api.net")
    #            conn.request("GET", path, "{body}", headers)
    #            response = conn.getresponse()
    #            payload = response.read()
    #            #            print(response.status, response.read())
    #            json_string = str(payload, "utf-8")
    #            elvia_response: ElviaWebResponse = ElviaWebResponse(
    #                response.status, json_string
    #            )
    #            conn.close()
    #            return elvia_response
    #        except Exception as e:
    #            print("[Errno {0}] {1}".format(e.errno, e.strerror))
    #        return None

    # pylint: disable=dangerous-default-value
    async def get_meter_values(
        self, metering_ids: list[str] = [], include_production: bool = False
    ) -> ElviaData:
        """Return ElviaData with recorded meter values."""

        params = urllib.parse.urlencode(
            {
                # Request parameters
                #    "startTime": "{string}",
                #    "endTime": "{string}",
                #    "meteringPointIds": "{array}",
                "includeProduction": include_production,
            }
        )

        response: ElviaWebResponse = await self.request_elvia_for_response(
            "/customer/metervalues/api/v1/metervalues?%s" % params
        )
        if response.status_code != 200:
            raise Exception("Response is not HTTP 200", response.json)

        meter_values: MeterValues = Pykson().from_json(response.json, MeterValues)
        return ElviaData(response.status_code, meter_values)

    # pylint: disable=dangerous-default-value
    async def get_max_hours(
        self, metering_ids: list[str] = [], include_production: bool = False
    ) -> ElviaData:
        """Return ElviaData with recorded max hours.

        This defines the monthly grid level.
        """

        params = urllib.parse.urlencode(
            {
                # Request parameters
                #           'calculateTime': '{string}',
                #           'meteringPointIds': '{array}',
                "includeProduction": include_production,
            }
        )

        response: ElviaWebResponse = await self.request_elvia_for_response(
            "/customer/metervalues/api/v2/maxhours?%s" % params
        )
        if response.status_code != 200:
            raise Exception("Response is not HTTP 200", response.json)

        max_hours: MaxHours = Pykson().from_json(response.json, MaxHours)
        return ElviaData(response.status_code, max_hours)


# if __name__ == "__main__":
#     TOKEN = ""
#     el = Elvia(TOKEN)
#     meterValue: MeterValues = asyncio.run(el.get_meter_values()).data
#     maxHours: MaxHours = asyncio.run(el.get_max_hours()).data
#     print(maxHours.meteringpoints[0].maxHoursAggregate[0].averageValue)
#     print(maxHours)
