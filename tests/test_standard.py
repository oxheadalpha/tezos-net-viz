def test_existance() -> None:
    import tezos_net_viz

    assert vars(tezos_net_viz)["__name__"] == "tezos_net_viz"
