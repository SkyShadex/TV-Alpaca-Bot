risk = 2
reward = 2
price = 2.38
cash = 1000
convertFact = 0.1


def calcRR(price):
    stopLoss = round((((convertFact*risk) * price) - price)*-1, 2)
    takeProfit = round((((convertFact*risk)*reward) * price) + price, 2)
    qty = cash / price
    projectedLoss = (stopLoss * qty) - cash
    projectedWin = (takeProfit * qty) - cash

    print("Stop Loss:", stopLoss)
    print("Take Profit:", takeProfit)
    print("Stop Loss Amount:", stopLoss * qty)
    print("Stop Loss $:", projectedLoss)
    print("Take Profit Amount:", takeProfit * qty)
    print("Take Profit $:", projectedWin)

    return stopLoss, takeProfit

calcRR(price)

stop = ((risk * price) - price)*-1

profit = (reward * price) + price


test = calcRR(price)