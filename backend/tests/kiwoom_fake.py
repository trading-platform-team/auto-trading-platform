"""테스트용 가짜 키움 서버 (httpx.MockTransport)

응답 형식은 키움 공식 명세 기준. 키 발급 후 실제 응답과 다르면 이 파일과 app/kiwoom만 맞추면 된다.
"""

import json

import httpx

VALID_KEYS = {"real-app": "real-secret", "mock-app": "mock-secret", "user-app": "user-secret"}

STOCKS = {
    "0": [{"code": "005930", "name": "삼성전자", "orderWarning": "0"},
          {"code": "000660", "name": "SK하이닉스", "orderWarning": "0"},
          {"code": "005935", "name": "삼성전자우", "orderWarning": "0"}],
    "10": [{"code": "035720", "name": "카카오", "orderWarning": "0"},
           {"code": "123456", "name": "위험종목", "orderWarning": "2"}],
}


class FakeKiwoom:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []  # (api-id, body)
        self.token_count = 0
        self.tokens: set[str] = set()
        self.assets = 10_000_000  # 추정예탁자산
        self.next_ord = 1
        self.orders: dict[str, dict] = {}
        self.fail_next: dict[str, tuple[int, int, str]] = {}  # api-id → (http, return_code, msg)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def ids(self) -> list[str]:
        return [a for a, _ in self.calls]

    def fill(self, ord_no: str, qty: int, price: int) -> None:
        self.orders[ord_no]["fills"].append((qty, price))

    def handle(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content or b"{}")
        if req.url.path == "/oauth2/token":
            if VALID_KEYS.get(body.get("appkey")) != body.get("secretkey"):
                return httpx.Response(200, json={"return_code": 3, "return_msg": "인증 실패"})
            self.token_count += 1
            tok = f"tok{self.token_count}"
            self.tokens.add(tok)
            return httpx.Response(200, json={"token": tok, "token_type": "bearer", "expires_dt": "20991231235959",
                                             "return_code": 0, "return_msg": "정상"})

        api_id = req.headers.get("api-id")
        self.calls.append((api_id, body))
        if req.headers.get("authorization", "").removeprefix("Bearer ") not in self.tokens:
            return httpx.Response(200, json={"return_code": 8005, "return_msg": "Token이 유효하지 않습니다"})
        if api_id in self.fail_next:
            status, code, msg = self.fail_next.pop(api_id)
            return httpx.Response(status, json={"return_code": code, "return_msg": msg})

        ok = {"return_code": 0, "return_msg": "정상적으로 처리되었습니다"}
        if api_id == "ka10001":
            if body["stk_cd"] == "999999":
                return httpx.Response(200, json={"return_code": 1902, "return_msg": "종목 정보가 없습니다"})
            return httpx.Response(200, json={**ok, "stk_cd": body["stk_cd"], "stk_nm": "삼성전자",
                                             "cur_prc": "+72000", "open_pric": "+71000", "high_pric": "+72500",
                                             "low_pric": "-70500", "base_pric": "71000", "pred_pre": "+1000",
                                             "flu_rt": "+1.41", "trde_qty": "1234567"})
        if api_id == "ka10095":  # 여러 종목 현재가 (StockService)
            names = {it["code"]: it["name"] for items in STOCKS.values() for it in items}
            rows = [{"stk_cd": c, "stk_nm": names.get(c, c), "cur_prc": "+72000", "pred_pre": "+1000",
                     "flu_rt": "+1.41", "trde_qty": "1234567"} for c in body["stk_cd"].split("|")]
            return httpx.Response(200, json={**ok, "atn_stk_infr": rows})
        if api_id == "ka10099":
            items = STOCKS.get(body["mrkt_tp"], [])
            if body["mrkt_tp"] == "0" and req.headers.get("cont-yn") != "Y":  # 코스피는 2페이지
                return httpx.Response(200, json={**ok, "list": items[:2]}, headers={"cont-yn": "Y", "next-key": "p2"})
            if body["mrkt_tp"] == "0":
                return httpx.Response(200, json={**ok, "list": items[2:]}, headers={"cont-yn": "N"})
            return httpx.Response(200, json={**ok, "list": items})
        if api_id == "kt00018":
            return httpx.Response(200, json={**ok, "tot_pur_amt": "1000000", "tot_evlt_amt": "1050000",
                                             "tot_evlt_pl": "50000", "tot_prft_rt": "5.00",
                                             "prsm_dpst_aset_amt": str(self.assets),
                                             "acnt_evlt_remn_indv_tot": [
                                                 {"stk_cd": "A005930", "stk_nm": "삼성전자", "rmnd_qty": "000000000014",
                                                  "trde_able_qty": "000000000014", "pur_pric": "000000071428",
                                                  "cur_prc": "000000075000", "evlt_amt": "000001050000",
                                                  "evltv_prft": "000000050000", "prft_rt": "5.00"}]})
        if api_id == "kt00001":
            return httpx.Response(200, json={**ok, "entr": "000008950000", "ord_alow_amt": "000008900000",
                                             "d2_entra": "000008950000"})
        if api_id in ("kt10000", "kt10001"):
            no = f"{self.next_ord:07d}"
            self.next_ord += 1
            self.orders[no] = {"body": body, "fills": []}
            return httpx.Response(200, json={**ok, "ord_no": no, "dmst_stex_tp": "KRX"})
        if api_id == "kt10003":
            return httpx.Response(200, json={**ok, "ord_no": f"{self.next_ord:07d}",
                                             "base_orig_ord_no": body["orig_ord_no"]})
        if api_id == "kt00009":
            rows = [{"ord_no": no, "stk_cd": o["body"]["stk_cd"], "ord_qty": o["body"]["ord_qty"],
                     "cntr_qty": str(q), "cntr_uv": str(p)}
                    for no, o in self.orders.items() for q, p in o["fills"]]
            return httpx.Response(200, json={**ok, "acnt_ord_cntr_prst_array": rows})
        return httpx.Response(200, json={"return_code": 8104, "return_msg": f"미지원 API {api_id}"})


class FakeWs:
    """가짜 실시간 WebSocket. script의 메시지를 차례로 내보내고 보낸 메시지를 sent에 남긴다."""

    def __init__(self, script: list[dict]):
        self.script = [json.dumps(m) for m in script]
        self.sent: list[dict] = []
        self.closed = False

    def __call__(self, url):  # connect(url) 대신
        self.url = url
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.closed = True

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def recv(self):
        return self.script.pop(0)

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.script:
            raise StopAsyncIteration
        return self.script.pop(0)
