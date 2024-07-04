from constants import O_FUTL, S_DATA


def input():
    """
    reads universe csv file
    """
    # TODO
    """
    Reads universe csv file from data folder
    """
    df = O_FUTL.get_df_fm_csv(S_DATA, "universe.csv", [])
    print(df)
    return df


def output():
    """
    writes out.csv to file
    """
    input_df = input()
    df = input_df.to_csv(S_DATA + "out.csv", index=False)
    dct = df.to_dict(orient="records")
    return dct


def main():
    dct = output()
    return dct
