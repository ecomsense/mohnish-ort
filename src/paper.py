import pandas as pd
from stock_brokers.bypass.bypass import Bypass
from constants import O_FUTL, S_DATA
import pendulum as plum


class Paper(Bypass):
    cols = [
        "broker_timestamp",
        "side",
        "filled_quantity",
        "symbol",
        "remarks",
        "average_price",
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._orders = pd.DataFrame()
        if O_FUTL.is_file_not_2day(S_DATA + "orders.csv"):
            O_FUTL.nuke_file(S_DATA + "orders.csv")

    @property
    def orders(self):
        return self._orders

    def order_cancel(self, **args):
        pass

    def order_place(self, **position_dict):
        try:
            if position_dict["order_type"] == "MKT":
                args = dict(
                    broker_timestamp=plum.now().format("YYYY-MM-DD HH:mm:ss"),
                    side=position_dict["side"],
                    filled_quantity=int(position_dict["quantity"]),
                    symbol=position_dict["symbol"],
                    remarks=position_dict["tag"],
                    average_price=0,
                )
                """
                ret = self.finvasia.searchscrip("NFO", position_dict["symbol"])
                if ret is not None:
                    token = ret["values"][0]["token"]
                    args["average_price"] = ApiHelper().scriptinfo(self, "NFO", token)
                """
                df = pd.DataFrame(columns=self.cols, data=[args])

                if not self._orders.empty:
                    df = pd.concat([self._orders, df], ignore_index=True)
                self._orders = df
        except Exception as e:
            print(f"{e} exception while placing order")

    def order_modify(self, **args):
        if not args.get("order_type", None):
            args["order_type"] = "MKT"

        if args["order_type"] == "MKT":
            self.order_place(**args)
        else:
            print(
                "order modify for other order types not implemented for paper trading"
            )

    def _ord_to_pos(self, df):
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
            else (row["average_price_buy"] - row["filled_quantity_sell"])
            * row["quantity"],
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

    @property
    def positions(self):
        lst = []
        df = self.orders
        df.to_csv(S_DATA + "orders.csv", index=False)
        if not self.orders.empty:
            df = self._ord_to_pos(df)
            lst = df.to_dict(orient="records")
        return lst
