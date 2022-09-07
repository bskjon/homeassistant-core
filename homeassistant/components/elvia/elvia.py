"""elvia communication."""
from __future__ import annotations

import datetime
from typing import Any
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


class CostTimeSpan:
    """Elvia cost time span."""

    start_time: float = 0.0
    end_time: float = 0.0
    cost: float = 0.0

    def __init__(self, start_time: float, end_time: float, cost: float) -> None:
        """Class init."""
        self.start_time = start_time
        self.end_time = end_time
        self.cost = cost


class Meter:
    """Data class for storing info."""

    success: bool = False
    status_code: int = 404
    meter_ids: list[str]

    def __init__(self, status_code: int, meter_ids: list[str]) -> None:
        """Class init."""
        self.success = status_code == 200
        self.status_code = status_code
        self.meter_ids = meter_ids


class ElviaData:
    """Data class for wrapping deserialized result."""

    status_code: int = 404
    data: MaxHours | MeterValues | Meter | None = None

    def __init__(self, status_code: int, data: Any) -> None:
        """Class init. Returns nothing."""
        self.status_code = status_code
        self.data = data


class Elvia:
    """Communication class for elvia."""

    domain = "elvia.azure-api.net"
    jwt: str

    meter: Meter
    max_hours: MaxHours
    meter_values: MeterValues

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

    async def update_meters(self) -> None:
        """Return None. Executes request for meter ids."""
        meter_data = await self.get_meters()
        self.meter = meter_data

    async def update_max_hours(self) -> None:
        """Request update of max hours and store it in object/class."""
        elvia_data = await self.get_max_hours()
        if elvia_data.status_code != 200:
            raise Exception("Elvia response is not OK!", elvia_data.data)
        max_hours_data = elvia_data.data
        if isinstance(max_hours_data, MaxHours) and max_hours_data is not None:
            self.max_hours = max_hours_data

    async def update_meter_values(self) -> None:
        """Request update of meter values and store it in object/class."""
        elvia_data = await self.get_max_hours()
        if elvia_data.status_code != 200:
            raise Exception("Elvia response is not OK!", elvia_data.data)
        meter_values = elvia_data.data
        if isinstance(meter_values, MeterValues) and meter_values is not None:
            self.meter_values = meter_values

    async def get_meters(self) -> Meter:
        """Return Meter with owned meter ids."""
        now = datetime.datetime.now(datetime.timezone.utc).replace(
            hour=0, minute=0, second=1, microsecond=0
        )

        params = urllib.parse.urlencode({"startTime": now.isoformat()})

        response: ElviaWebResponse = await self.request_elvia_for_response(
            "/customer/metervalues/api/v1/metervalues?%s" % params
        )

        if response.status_code != 200:
            raise Exception("Response is not OK", response.status_code, response.json)

        meter_values: MeterValues = Pykson().from_json(response.json, MeterValues)
        meters = meter_values.meteringpoints
        meter_ids = [item.metering_point_id for item in meters]

        return Meter(response.status_code, meter_ids)

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
            raise Exception("Response is not OK", response.status_code, response.json)

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

    def get_grid_level(self, kw: float) -> int:
        """Calculate the grid level based on kwh."""
        if kw <= 2:
            return 1
        if 5 >= kw > 2:
            return 2
        if 10 >= kw > 5:
            return 3
        if 15 >= kw > 10:
            return 4
        if 20 >= kw > 15:
            return 5
        if 25 >= kw > 20:
            return 6
        if 50 >= kw > 25:
            return 7
        if 75 >= kw > 50:
            return 8
        if 100 >= kw > 75:
            return 9
        return 10

    def get_cost_periods(self) -> dict[str, CostTimeSpan]:
        """Return instances of cost.

        Consists of keys: day, night, weekend
        weekend = saturday to sunday + holidays
        """
        return {
            "day": CostTimeSpan(6, 22, cost=43.10),
            "night": CostTimeSpan(22, 6, cost=36.85),
            "weekend": CostTimeSpan(0, 0, cost=36.85),
        }

    def get_cost_period_now(self) -> CostTimeSpan:
        """Return fixed grid cost for the current time."""
        periods = self.get_cost_periods()
        now = datetime.datetime.now()
        cost_time_span: CostTimeSpan
        if now.isoweekday() in [6, 7]:
            cost_time_span = periods["weekend"]
        elif now.hour >= periods["day"].start_time and (
            now.hour <= periods["day"].end_time and now.minute == 0
        ):
            cost_time_span = periods["day"]
        else:
            cost_time_span = periods["night"]

        return cost_time_span


# if __name__ == "__main__":
#     TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjVBMkIwMDFBODEzRkE3N0E5M0UxNERDNjU4QTNERjY1REIzRDFEM0VSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ildpc0FHb0VfcDNxVDRVM0dXS1BmWmRzOUhUNCJ9.eyJuYmYiOjE2NjE3ODczMTUsImV4cCI6MTgxOTQ2NzMxNSwiaXNzIjoiaHR0cHM6Ly9lbHZpZC5lbHZpYS5pbyIsImNsaWVudF9pZCI6IjU4ZmQ3Y2M3LTUyNzktNDYyZS05ZDg4LTEwNWM2MjU3OThiNiIsInN1YiI6IjcxODBjOGE2LWY3NTctNDJiMy1iZTFiLTQ4Yjg1MzhkMWFhMyIsImF1dGhfdGltZSI6MTY2MTc4NzMxNCwiaWRwIjoibG9jYWwiLCJiYW5raWRfcGlkIjoiOTU3OC01OTk5LTQtMzc4NDEzNSIsInRva2VuX2lkIjoiZmZmMDg2NTktMGEzZS00ZDAzLWE2MzMtMmUyODhmY2Q5YzAzIiwiaWF0IjoxNjYxNzg3MzE1LCJzY29wZSI6WyJrdW5kZS5hY2Nlc3MtaW5mb3JtYXRpb24uZGVsZWdhdGVkLXVzZXJhY2Nlc3MiLCJrdW5kZS5kZWxlZ2F0ZWQtdXNlcmFjY2VzcyIsImt1bmRlLm1ldGVydmFsdWVzLmRlbGVnYXRlZC11c2VyYWNjZXNzIl0sImFtciI6WyJkZWxlZ2F0aW9uIl19.i82Q64er_pFuvqc_emDISHPJK_cVt7tNMuNJMHB-Pq6kjHFsMZkkN81lei_g30pARWMe_bpH9N9qnzguIQ2WAlg9x6o1YPfl5OdTcRoBtv10YJd_N9gedDr6IURoC8I4XtZjuUsSBZeT-g0sRtBUFcO481eMpDTb_yHYL3RbKnORXaJeYGRzELqfP187_7eCJAw-8avSsom8aWx_-YAN1_iIiqnCMGI6Xsu6_bq0pYtE8LJo3w8zX1EtbRoXmWp_1j4NUGi_1W2WdR2S1fyGNu8HbggYx7d7tNQwzhp4ArBt6u810z3_9aKNjVUaLkr13eUumEKv_IjOfOLmoVcbIw"
#     el = Elvia(TOKEN)
#     print(asyncio.run(el.get_meters()).meter_ids)
#     meterValue: MeterValues = asyncio.run(el.get_meter_values()).data
#     maxHours: MaxHours = asyncio.run(el.get_max_hours()).data
#     print(maxHours.meteringpoints[0].maxHoursAggregate[0].averageValue)
#     print(maxHours)
