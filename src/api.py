from constants import O_SETG, logging, O_CNFG, S_DATA, O_FUTL
from typing import List
from traceback import print_exc
import pandas as pd
import pendulum as plum


def ord_to_pos(df):
    # Filter DataFrame to include only 'B' (Buy) side transactions
    buy_df = df[df["side"] == "B"]

    # Filter DataFrame to include only 'S' (Sell) side transactions
    sell_df = df[df["side"] == "S"]

    # Group by 'symbol' and sum 'filled_quantity' for 'B' side transactions
    buy_grouped = (
        buy_df.groupby("symbol")
        .agg({"filled_quantity": "sum", "average_price": "sum"})
        .reset_index()
    )
    # Group by 'symbol' and sum 'filled_quantity' for 'S' side transactions
    sell_grouped = (
        sell_df.groupby("symbol")
        .agg({"filled_quantity": "sum", "average_price": "sum"})
        .reset_index()
    )
    # Merge the two DataFrames on 'symbol' column with a left join
    result_df = pd.merge(
        buy_grouped,
        sell_grouped,
        on="symbol",
        suffixes=("_buy", "_sell"),
        how="outer",
    )

    result_df.fillna(0, inplace=True)
    # Calculate the net filled quantity by subtracting 'Sell' side quantity from 'Buy' side quantity

    result_df["quantity"] = (
        result_df["filled_quantity_buy"] - result_df["filled_quantity_sell"]
    )
    result_df["urmtom"] = result_df.apply(
        lambda row: 0
        if row["quantity"] == 0
        else (row["average_price_buy"] - row["filled_quantity_sell"]) * row["quantity"],
        axis=1,
    )
    result_df["rpnl"] = result_df.apply(
        lambda row: row["average_price_sell"] - row["average_price_buy"]
        if row["quantity"] == 0
        else 0,
        axis=1,
    )
    result_df.drop(
        columns=[
            "filled_quantity_buy",
            "filled_quantity_sell",
            "average_price_buy",
            "average_price_sell",
        ],
        inplace=True,
    )
    return result_df


def get_bypass():
    from omspy_brokers.bypass import Bypass

    try:
        dct = O_CNFG["bypass"]
        tokpath = S_DATA + dct["userid"] + ".txt"
        enctoken = None
        if not O_FUTL.is_file_not_2day(tokpath):
            print(f"{tokpath} modified today ... reading {enctoken}")
            with open(tokpath, "r") as tf:
                enctoken = tf.read()
                if len(enctoken) < 5:
                    enctoken = None
        print(f"enctoken to broker {enctoken}")
        bypass = Bypass(dct["userid"], dct["password"], dct["totp"], tokpath, enctoken)
        if bypass.authenticate():
            if not enctoken:
                enctoken = bypass.kite.enctoken
                with open(tokpath, "w") as tw:
                    tw.write(enctoken)
        else:
            raise Exception("unable to authenticate")
    except Exception as e:
        print(f"unable to create bypass object {e}")
    else:
        return bypass


def get_zerodha():
    try:
        from omspy_brokers.zerodha import Zerodha

        dct = O_CNFG["zerodha"]
        zera = Zerodha(
            user_id=dct["userid"],
            password=dct["password"],
            totp=dct["totp"],
            api_key=dct["api_key"],
            secret=dct["secret"],
            tokpath=S_DATA + dct["userid"] + ".txt",
        )
        if not zera.authenticate():
            raise Exception("unable to authenticate")

    except Exception as e:
        print(f"exception while creating zerodha object {e}")
    else:
        return zera


def remove_token(tokpath):
    __import__("os").remove(tokpath)


def login():
    if O_CNFG["broker"] == "bypass":
        return get_bypass()
    else:
        return get_zerodha()


class Helper:
    api = None
    buy = []
    short = []
    orders = []

    @classmethod
    def set_api(cls):
        if cls.api is None:
            cls.api = login()

    @classmethod
    def exit(cls, buy_or_short: str):
        try:
            lst = cls.buy if buy_or_short == "buy" else cls.short
            print(f"exiting {buy_or_short}")

            if any(lst):
                for i in lst:
                    side = i.pop("side")
                    i["side"] = "S" if side == "B" else "B"
                    i["tag"] = "exit"
                    if CMMN["live"]:
                        resp = cls.api.order_place(**i)
                        print(resp)
                    else:
                        cls.orders.append(i)

                if buy_or_short == "buy":
                    cls.buy = []
                else:
                    cls.short = []
        except Exception as e:
            logging.error(f"exit: {e}")
            print_exc()

    @classmethod
    def enter(cls, buy_or_short: str, orders: List):
        """
        param orders:
            contains dictionary with keys
            symbol, side, quantity, price, trigger_price
        """
        try:
            print(f"entering {buy_or_short}")
            lst = cls.buy if buy_or_short == "buy" else cls.short
            for o in orders:
                o["validity"] = "DAY"
                o["product"] = "NRML"
                logging.debug(o)
                if CMMN["live"]:
                    resp = cls.api.order_place(**o)
                    print(resp)
                else:
                    args = [
                        {
                            "exchangeSegment": 2,
                            "exchangeInstrumentID": o["symbol"].split("|")[-1],
                        }
                    ]
                    o["broker_timestamp"] = plum.now().format("YYYY-MM-DD HH:mm:ss")
                    o["average_price"] = Helper.get_ltp(args)
                    o["filled_quantity"] = o.pop("quantity")
                    o["tag"] = "enter"
                    cls.orders.append(o)
                lst.append(o)
        except Exception as e:
            logging.error(f"enter: {e}")
            print_exc()

    @classmethod
    def positions(cls):
        if O_SETG["live"]:
            return cls.api.positions
        elif any(cls.orders):
            df = pd.DataFrame(cls.orders)
            df.to_csv(S_DATA + "orders.csv", index=False)
            df = ord_to_pos(df)
            lst = df.to_dict(orient="records")
            return lst
        else:
            return []


if __name__ == "__main__":
    Helper.set_api()
    resp = Helper.api.positions
    pd.DataFrame(resp).to_csv(S_DATA + "positions.csv", index=False)

    resp = Helper.api.orders
    pd.DataFrame(resp).to_csv(S_DATA + "orders.csv", index=False)
