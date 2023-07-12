from components.api_alpaca import api as alpaca

def alpaca_rebalance(target_allocations, cash_weight=.05):

    portfolio_symbols = list(target_allocations.keys())

    # Check to Make Sure All Symbols are Eligible for Fractional Trading on Alpaca and Market is Open
    all_symbols_eligible_for_fractionals = _all_symbols_eligible_for_fractionals(portfolio_symbols)

    # Ensures All Symbols are Fractionable and the Market is Open
    if all_symbols_eligible_for_fractionals and alpaca.get_clock().is_open:

        # Grab Current Alpaca Holdings
        alpaca_latest_positions = _alpaca_latest_positions()

        # Construct a List of Equities to Close Based on Current Alpaca Holdings and Current Desired Holdings
        print("Closing Positions...")
        print(20*"~~")
        alpaca_symbols_to_close = _alpaca_symbols_to_close(alpaca_latest_positions, portfolio_symbols)
        
        # Close Any Alpaca Positions if Neccessary
        if alpaca_symbols_to_close:
            alpaca_close_positions(alpaca_symbols_to_close)

        # Calculate Rebalance Weight Taking Cash Weight % into Account
        print("Preparing Rebalance Equity...")
        print(20*"~~")
        rebalance_equity = _rebalance_equity(cash_weight)
        
        # Allocate the Equity to Each Holding Based on Weight and Available Portfolio Equity
        print("Preparing Positions to Sell and Buy...")
        print(20*"~~")
        portfolio_symbols_equity_allocations = _portfolio_symbols_equity_allocations(target_allocations, rebalance_equity)
        latest_alpaca_positions_allocations = _alpaca_latest_positions_allocations()
        positions_to_sell, positions_to_buy = _alpaca_symbols_to_sell_and_buy(portfolio_symbols_equity_allocations, latest_alpaca_positions_allocations)

        # Finally Adjust Allocations 
        print("Rebalancing...")
        print(20*"~~")
        handle_sell_orders(positions_to_sell)
        handle_buy_orders(positions_to_buy)

        print("Completed Rebalance!")
        print(20*"~~")

target_allocations = {"VOO": .2, "VGT": .2, "QQQ": .2, "VTI": .2, "VYM": .2}

alpaca_rebalance(target_allocations)