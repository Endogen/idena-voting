import requests
import logging


class IdenaAPI:

    base_url = "https://api.idena.io/api/"
    timeout = 3  # Seconds

    def __init__(self, base_url=None, timeout=None):
        if base_url:
            self.base_url = base_url
        if timeout:
            self.timeout = timeout

    def _request(self, url, params, timeout=None):
        timeout = self.timeout if not timeout else timeout

        try:
            return requests.get(url, params=params, timeout=timeout).json()
        except Exception as e:
            return {"error": {"message": str(e), "code": 0}}

    def transactions_for(self, address):
        url = f"{self.base_url}address/{address}/txs"
        transactions = list()
        steps = 50
        skip = 0

        loop = True
        while loop:
            trx_list = self._request(url, {"skip": skip, "limit": steps})

            if "error" in trx_list:
                logging.error(trx_list["error"]["message"])
                return transactions
            if not trx_list or not trx_list["result"]:
                return transactions

            transactions.extend(trx_list["result"])

            if len(trx_list["result"]) < steps:
                loop = False

            skip += steps

        return transactions

    def is_verified(self, address):
        url = f"{self.base_url}identity/{address}"
        identity = self._request(url, None)

        if "result" in identity:
            if "state" in identity["result"]:
                if identity["result"]["state"] in ["Human", "Verified"]:
                    return True

        return False
