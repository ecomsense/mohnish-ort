from traceback import print_exc

import pandas as pd
import pendulum as plum
from stock_brokers.bypass.bypass import Bypass

from constants import O_FUTL, S_DATA, logging
from utils import generate_unique_id


class Paper(Bypass):
    cols = [
        "order_id",
        "broker_timestamp",
        "side",
        "filled_quantity",
        "symbol",
        "remarks",
        "average_price",
    ]

    def __init__(
        self,
        userid,
        password,
        totp,
        tokpath,
        enctoken,
    ):
        super().__init__(userid, password, totp, tokpath, enctoken)
        self._orders = pd.DataFrame()
        if O_FUTL.is_file_not_2day(S_DATA + "orders.csv"):
            O_FUTL.nuke_file(S_DATA + "orders.csv")

    @property
    def orders(self):
        list_of_orders = self._orders
        pd.DataFrame(list_of_orders).to_csv(S_DATA + "orders.csv", index=False)
        return list_of_orders.to_dict(orient="records")

    def order_cancel(self, **args):
        if args.get("order_id", None):
            self._orders = self._orders[self._orders["order_id"] != args["order_id"]]
            _ = self.orders

    def order_place(self, **position_dict):
        try:
            if not position_dict.get("order_id", None):
                order_id = generate_unique_id()
            else:
                order_id = position_dict["order_id"]

            average_price = (
                position_dict["last_price"]
                if position_dict["order_type"][0].upper() == "M"
                else position_dict["trigger_price"]
            )
            status = (
                "COMPLETE"
                if position_dict["order_type"][0].upper() == "M"
                else "TRIGGER PENDING"
            )
            args = dict(
                order_id=order_id,
                broker_timestamp=plum.now().format("YYYY-MM-DD HH:mm:ss"),
                side=position_dict["side"],
                filled_quantity=int(position_dict["quantity"]),
                symbol=position_dict["symbol"],
                remarks=position_dict["tag"],
                average_price=average_price,
                status=status,
            )
            df = pd.DataFrame(columns=self.cols, data=[args])

            if not self._orders.empty:
                df = pd.concat([self._orders, df], ignore_index=True)
            self._orders = df
            return order_id
        except Exception as e:
            logging.error(f"{e} exception while placing order")
            print_exc()

    def order_modify(self, args):
        if not args.get("order_type", None):
            args["order_type"] = "MARKET"

        if args["order_type"][0].upper() == "M":
            # drop row whose order_id matches
            args["tag"] = "modify"
            self._orders = self._orders[self._orders["order_id"] != args["order_id"]]
            self.order_place(**args)
        else:
            logging.info(
                "order modify for other order types not implemented for paper trading"
            )
            # TODO FIX THIS
            raise NotImplementedError(
                "order modify for other order types not implemented"
            )

    def _ord_to_pos(self, df):
        # Filter DataFrame to include only 'B' (Buy) side transactions
        buy_df = df[df["side"] == "BUY"]

        # Filter DataFrame to include only 'S' (Sell) side transactions
        sell_df = df[df["side"] == "SELL"]

        # Group by 'symbol' and sum 'filled_quantity' and 'average_price' for 'B' side transactions
        buy_grouped = (
            buy_df.groupby("symbol")
            .agg({"filled_quantity": "sum", "average_price": "sum"})
            .reset_index()
        )

        # Group by 'symbol' and sum 'filled_quantity' and 'average_price' for 'S' side transactions
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
        print(result_df)
        # Fill NaN values with 0
        result_df.fillna(0, inplace=True)

        # Calculate the net filled quantity by subtracting 'Sell' side quantity from 'Buy' side quantity
        result_df["quantity"] = (
            result_df["filled_quantity_buy"] - result_df["filled_quantity_sell"]
        )

        # Calculate the unrealized mark-to-market (urmtom) value
        result_df["urmtom"] = result_df.apply(
            lambda row: (
                0
                if row["quantity"] == 0
                else (row["average_price_buy"] - row["average_price_sell"])
                * row["quantity"]
            ),
            axis=1,
        )

        # Calculate the realized profit and loss (rpnl)
        result_df["rpnl"] = result_df.apply(
            lambda row: (
                row["average_price_sell"] - row["average_price_buy"]
                if row["quantity"] == 0
                else 0
            ),
            axis=1,
        )

        # Drop intermediate columns
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
        try:
            lst = []
            df = pd.read_csv(S_DATA + "orders.csv")
            if not df.empty:
                df = self._ord_to_pos(df)
                print(df)
                lst = df.to_dict(orient="records")
        except Exception as e:
            logging.debug(f"positions error: {e}")
        finally:
            return lst


if __name__ == "__main__":
    from api import Helper

    help = Helper(15)
    orders = pd.read_csv(S_DATA + "orders.csv").to_dict(orient="records")
    print(orders)

    filtered_orders = [
        order for order in orders if order["status"] != "TRIGGER PENDING"
    ]

    pd.DataFrame(filtered_orders).to_csv(S_DATA + "orders.csv", index=False)
    print(help.api().positions)
