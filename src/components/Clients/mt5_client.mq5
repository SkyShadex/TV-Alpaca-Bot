//+------------------------------------------------------------------+
//|                                                    SkyBot_TV.mq5 |
//|                                                        SkyShadex |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#include<Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#define GV_DRAWDOWN "GVDRAWDOWN"
#define GV_OVERRIDE "OVERRIDE"
#define GV_PERMITTEDLOSS "RISK"
CTrade trade;
CSymbolInfo syminfo;
#property script_show_inputs

input string   Address = "localhost";
input int      Port = 5000;
input int      Pyramid = 5;
double         Risk = 0.25;
input double   Reward = 3;
input double   Lot_Override = 0;
input double   StopLossPoints = 300;
input double   HedgeGap = 0.005;
bool           Hedge_Enable = false;
datetime       previousDateTime = 0;
bool           isDrawdown;
bool           ExtTLS =false;
double         upperLine, lowerLine, equityMax;
double         HedgeTPFactor = 1.5;
int            debug = 0;
int            lastErrorTime = 0;
int            Eventtimer = 1;
double         downbad = 0;

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double            round_down(double v, double to)
  {
   return to * MathFloor(v / to);
  }
/// Round a double to a multiple of an amount.
double            round_up(double v, double to)
  {
   return to * MathCeil(v / to);
  }
/// Round a double to a multiple of an amount.
double            round_nearest(double v, double to)
  {
   return to * MathRound(v / to);
  }



//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int OnInit()
  {
   GlobalVariableSet(GV_PERMITTEDLOSS,10000);
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
//--- destroy the timer after completing the work
  }
//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(lastErrorTime>5)
     {
      int i = 60;
      lastErrorTime = 5;
      EventKillTimer();
      Eventtimer+=20;
      if(Eventtimer>i)
         Eventtimer=i;
      EventSetTimer(Eventtimer);
      Print(__FUNCTION__," ",Eventtimer," ",lastErrorTime);
     }
   else
      if(lastErrorTime == 0)
        {
         if(Eventtimer > 1)
            Eventtimer-=10;
        }
      else
        {
         Eventtimer = 1;
        }

   drawdownSafety();
   hedgePrint();
   socketSystem();
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnTick()
  {


  }


//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double StartingBalance = 200000;
double maxDDP_Limit = 8;
double dailyDDP_Limit = 4;
void drawdownSafety()
  {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > equityMax)
     {
      equityMax = equity;
     }
   double dailyDDP = NormalizeDouble((equityMax-equity) / equityMax * 100,2);
//double maxDDP = NormalizeDouble((equityMax-equity) / StartingBalance * 100,2);
//Print(equityMax,"/",dailyDDP,"/",maxDDP);
   if(GlobalVariableCheck(GV_OVERRIDE)&&GlobalVariableGet(GV_OVERRIDE)>-10)
     {
      int mddoverride =GlobalVariableGet(GV_OVERRIDE);
      mddoverride--;
      Print(__FUNCTION__,": Manual Override. Resetting drawdown...");
      equityMax = 0;
      equity = 0;
      isDrawdown = false;
      GlobalVariableDel(GV_DRAWDOWN);
      if(mddoverride>0)
         GlobalVariableSet(GV_OVERRIDE,mddoverride);
      if(mddoverride<=0)
         GlobalVariableDel(GV_OVERRIDE);
     }
   else
     {
      if(GlobalVariableCheck(GV_DRAWDOWN))
        {
         isDrawdown = true;
         double gv_drawdown = GlobalVariableGet(GV_DRAWDOWN);
         if(gv_drawdown> equityMax)
            equityMax = gv_drawdown;
        }
      int bars = iBars(_Symbol,PERIOD_D1);
      static int barsTotal = bars;
      if(barsTotal != bars && GlobalVariableCheck(GV_DRAWDOWN))
        {
         Print(__FUNCTION__,": New day. Resetting drawdown...");
         equityMax = equity;
         isDrawdown = false;
         GlobalVariableDel(GV_DRAWDOWN);
        }
      if(isDrawdown || dailyDDP >= dailyDDP_Limit)
        {
         CloseAllOrders();
         CloseAllPositions();
         isDrawdown = true;
         downbad = GlobalVariableGet(GV_PERMITTEDLOSS);
         GlobalVariableSet(GV_DRAWDOWN,equityMax);
        }
     }

   Comment("\n\nMax Drawdown: ",dailyDDP,"%."," Status: ",isDrawdown);
  }



//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void serverClock()
  {
//--- time of the OnTimer() first call
   static datetime start_time=TimeCurrent();
//--- trade server time during the first OnTimer() call
   static datetime start_tradeserver_time=0;
//--- calculated trade server time
   static datetime calculated_server_time=0;
//--- local PC time
   datetime local_time=TimeLocal();
//--- current estimated trade server time
   datetime trade_server_time=TimeTradeServer();
//--- if a server time is unknown for some reason, exit ahead of time
   if(trade_server_time==0)
      return;
//--- if the initial trade server value is not set yet
   if(start_tradeserver_time==0)
     {
      start_tradeserver_time=trade_server_time;
      //--- set a calculated value of a trade server
      Print(trade_server_time);
      calculated_server_time=trade_server_time;
     }
   else
     {
      //--- increase time of the OnTimer() first call
      if(start_tradeserver_time!=0)
         calculated_server_time=calculated_server_time+1;;
     }
//---
   string com=StringFormat("Start time: %s\r\n",TimeToString(start_time,TIME_MINUTES|TIME_SECONDS));
   com=com+StringFormat("Local time: %s\r\n",TimeToString(local_time,TIME_MINUTES|TIME_SECONDS));
   com=com+StringFormat("TimeTradeServer time: %s\r\n",TimeToString(trade_server_time,TIME_MINUTES|TIME_SECONDS));
   com=com+StringFormat("EstimatedServer time: %s\r\n",TimeToString(calculated_server_time,TIME_MINUTES|TIME_SECONDS));
//--- display values of all counters on the chart
   Comment(com);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void hedgePrint()
  {
   if(!Hedge_Enable)
      return;
   Comment("Upper Hedge Level: ",DoubleToString(upperLine,_Digits),"\nLower Hedge Level: ",DoubleToString(lowerLine,_Digits));
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void hedgeLine()
  {
   if(!Hedge_Enable)
      return;

   double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);
   upperLine = bid + (bid * (HedgeGap/100));
   lowerLine = bid - (bid * (HedgeGap/100));

  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void hedgeReset()
  {
   if(!Hedge_Enable)
      return;

   upperLine = 0;
   lowerLine = 0;
//Print("Hedge lines Reset");

  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void hedgeOrder(double lots)
  {
   if(!Hedge_Enable)
      return;
   if(countPositons()>=0)
     {
      double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);
      if(bid < lowerLine && lowerLine != 0 && upperLine != 0)
        {
         double stop = NormalizeDouble(upperLine,_Digits);
         double takeprofit = NormalizeDouble(bid*(0.997),_Digits);
         double biggerlots = NormalizeDouble(lots*2,_Digits);
         if(debug==0)
           {
            trade.Sell(biggerlots,_Symbol,0,stop,takeprofit,NULL);
           }
         hedgeReset();
        }
     }
  }


//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void Parse(string payload)
  {
   int timestampIndex = StringFind(payload, "Timestamp:");
   int commaIndex = StringFind(payload, ",", timestampIndex);
   string timestampStr = StringSubstr(payload, timestampIndex + 11, commaIndex - timestampIndex - 11);
   double timestamp = StringToDouble(timestampStr);
   datetime dateTime = timestamp;
   int symbolIndex = StringFind(payload, "Symbol:");
   int sideIndex = StringFind(payload, "Side:", symbolIndex);
   string symbol = StringSubstr(payload, symbolIndex + 8, sideIndex - symbolIndex - 8);
   int priceIndex = StringFind(payload, "Price:");
   int quantityIndex = StringFind(payload, "Quantity:", priceIndex);
   string side = StringSubstr(payload, sideIndex + 5, priceIndex - sideIndex - 5);
   int commentIndex = StringFind(payload, "Comment:");
   int orderIDIndex = StringFind(payload, "Order ID:", commentIndex);
   string priceStr = StringSubstr(payload, priceIndex + 6, quantityIndex - priceIndex - 6);
   double price = StringToDouble(priceStr);
   string quantityStr = StringSubstr(payload, quantityIndex + 10, commentIndex - quantityIndex - 10);
   double quantity = StringToDouble(quantityStr);
   string comment = StringSubstr(payload, commentIndex + 9, orderIDIndex - commentIndex - 9);
   string orderID = StringSubstr(payload, orderIDIndex + 9);
//Print("Symbol:", symbol, _Symbol);

//string symCheck = _Symbol;

   string symbolPrefix = StringSubstr(symbol, 0, 4);
   string _SymbolPrefix = StringSubstr(_Symbol, 0, 4);
//Print(symbolPrefix,_SymbolPrefix);

   if(dateTime != previousDateTime && symbolPrefix == _SymbolPrefix)
     {
      // Print the extracted variables
      Print("");
      Print("<=========================== New Order =====================================>");
      Print(_Symbol,": ",side, "Price:", DoubleToString(price));
      previousDateTime = dateTime;
      if(Pyramid<=countPositons() && StringFind(side, "buy") >= 0)
        {
         Print("Max Positions Reached!");
         return;
        }
      pushOrder(side, price);
     }
   
  }



//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void pushOrder(string side,double price_signal)
  {
   double ticksize = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double ask = SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread = SymbolInfoInteger(_Symbol,SYMBOL_SPREAD)*ticksize;
   double price = NormalizeDouble(price_signal,_Digits);
   double source = price;
   if(price>ask*0.995)
     {
      source = ask;
     }

   double newprice = MathMax(ask,source);
   double sl = NormalizeDouble((newprice - StopLossPoints * ticksize)-spread,_Digits);
   double slDistance = newprice - sl;
   Print(__FUNCTION__,": ",newprice,"/",sl,"/",slDistance);
   double tp = NormalizeDouble(newprice + MathAbs(slDistance*Reward),_Digits);
   double lots = calcLots(slDistance);
   if(StringFind(side, "buy") >= 0)
     {
      if(Lot_Override != 0)
        {
         lots = Lot_Override;
        }
      if(sl > newprice)
        {
         sl=0;
         tp=0;
        }
      Print(_Symbol," [Order Payload]: ","Ask: ",ask,", Bid: ",bid,", Spread: ",spread,", Price: ",price," ===================================>"," [Order Payload]: ","New Price: ",newprice,", SL: ",sl," TP: ",tp,", Lots: ",lots," ===================================>");
      Print("Order Placed");

      hedgeOrder(lots);
      if(debug==0)
        {
         trade.BuyLimit(lots,newprice,_Symbol,sl,tp,ORDER_TIME_GTC,0,NULL);
        }
      hedgeLine();

     }

   if(StringFind(side, "sell") >= 0)
     {
      CloseAllOrders();
      CloseAllPositions();
     }

  }


//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int countPositons()
  {
   int positions = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetString(POSITION_SYMBOL) == _Symbol)
        {
         positions++;
        }
     }
   return positions;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CloseAllPositions()
  {
   bool positionsClosed = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetString(POSITION_SYMBOL) == _Symbol)
        {
         trade.PositionClose(ticket);
         positionsClosed = true;
        }
     }
   if(positionsClosed)
     {
      Print(_Symbol,": Closing Positions");
      hedgeReset();
     }
   else
     {
      Print(_Symbol,": No Open Positions Found");
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CloseAllOrders()
  {
   bool ordersClosed = false;
   int ord_total=OrdersTotal();
   if(ord_total > 0)
     {
      for(int i = ord_total - 1; i >= 0; i--)
        {
         ulong ticket=OrderGetTicket(i);
         if(OrderSelect(ticket) && OrderGetString(ORDER_SYMBOL)==_Symbol)
           {
            trade.OrderDelete(ticket);
            ordersClosed = true;
           }
        }
     }
   if(ordersClosed)
     {
      Print(_Symbol,": Closing Orders");
      hedgeReset();
     }
   else
     {
      Print(_Symbol,": No Open Orders Found");
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int HistoryDealGetStreak()
  {
//---
   HistorySelect(iTime(_Symbol,PERIOD_D1,0),TimeCurrent());
   int total=HistoryDealsTotal();
   ulong ticket;
   int wins=0;
   for(int i=total-1; i>=0; i--)
     {
      if((ticket=HistoryDealGetTicket(i))>0)
        {
         if(HistoryDealGetDouble(ticket,DEAL_PROFIT)<0)
            return(WRONG_VALUE);
         wins++;
        }
     }
//---
   return(wins);
  }

//+------------------------------------------------------------------+
//|    Calculate Lot Size                                            |
//+------------------------------------------------------------------+
double calcLots(double slDistance)
  {
   double ticksize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickvalue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double lotstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minvolume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxvolume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double risk_Local = Risk;

   Print(__FUNCTION__,": ",ticksize,"/",tickvalue,"/",lotstep,"/",minvolume,"/",maxvolume,"/",slDistance);

//int consecutiveWins = HistoryDealGetStreak();

//if(consecutiveWins > 0)
//  {
//   Print("Consecutive Wins: ", consecutiveWins);
//   // Increase lot size logarithmically on each consecutive win
//   risk_Local *= MathLog(consecutiveWins + 1);
//   Print("Increasing Risk: ",risk_Local);
//  }



   if(ticksize == 0 || tickvalue == 0 || lotstep == 0)
     {
      Print(__FUNCTION__, 1, " > Lotsize cannot be calculated...");
      return 0;
     }

   double riskMoney = riskManager() * (risk_Local / 100);
   Print("Risking $",riskMoney,"...");
   double moneyPerLotStep = slDistance / ticksize * tickvalue * lotstep;
   Print("Risk per Lot Step: $",moneyPerLotStep);

   if(moneyPerLotStep == 0)
     {
      Print(__FUNCTION__, 2, " > Lotsize cannot be calculated...");
      return 0;
     }

   double lots = (riskMoney / moneyPerLotStep) * lotstep;
//Print("Lots: ",lots);
   lots = MathAbs(lots);
//Print("Lots: ",lots);
   if(maxvolume != 0)
      lots = MathMin(lots, maxvolume);
   if(minvolume != 0)
      lots = MathMax(lots, minvolume);

   lots = NormalizeDouble(lots,2);
//Print("Lots: ",lots);
// Print(lots);
   return lots;
  }


//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double riskManager()
  {
   if(downbad!=0)
     {
      Print("Downbad... $",downbad);
      return downbad;
     }
   return AccountInfoDouble(ACCOUNT_BALANCE);
  }


//+------------------------------------------------------------------+
//| Send command to the server                                       |
//+------------------------------------------------------------------+
bool HTTPSend(int socket,string request)
  {
   char req[];
   int  len=StringToCharArray(request,req)-1;
   if(len<0)
      return(false);
//--- if secure TLS connection is used via the port 443
   if(ExtTLS)
      return(SocketTlsSend(socket,req,len)==len);
//--- if standard TCP connection is used
   return(SocketSend(socket,req,len)==len);
  }
//+------------------------------------------------------------------+
//| Read server response                                             |
//+------------------------------------------------------------------+
string HTTPRecv(int socket, uint timeout)
  {
   char rsp[];
   string result;
   uint timeout_check = GetTickCount() + timeout;
// Read data from sockets until they are still present but not longer than timeout
   do
     {
      uint len = SocketIsReadable(socket);
      if(len)
        {
         int rsp_len;
         // Various reading commands depending on whether the connection is secure or not
         if(ExtTLS)
            rsp_len = SocketTlsRead(socket, rsp, len);
         else
            rsp_len = SocketRead(socket, rsp, len, timeout);
         // Analyze the response
         if(rsp_len > 0)
           {
            result += CharArrayToString(rsp, 0, rsp_len);
            // Check if the entire response has been received
            int header_end = StringFind(result, "\r\n\r\n");
            if(header_end > 0)
              {
               // Extract the header and body
               string header = StringSubstr(result, 0, header_end);
               string body = StringSubstr(result, header_end + 4); // +4 to skip the "\r\n\r\n" characters
               //Print("HTTP answer header received:");
               //Print(body);
               return(body);
              }
           }
        }
     }
   while(GetTickCount() < timeout_check && !IsStopped());

   string error = "";
   if(GetTickCount() - lastErrorTime > 5 * 1000)  // Rate-limit retries to once every 5 seconds
     {
      lastErrorTime = GetTickCount();
      error = "Error occurred while reading server response";
     }

   return error;
  }


//+------------------------------------------------------------------+
//|          Handle Socket                                           |
//+------------------------------------------------------------------+
void socketSystem()
  {
   int socket = SocketCreate();
   if(socket == INVALID_HANDLE)
     {
      Print("Failed to create a socket, error ", GetLastError());
      return;
     }

// Connect to the server
   if(!SocketConnect(socket, Address, Port, 1500))
     {
      Print("Connection to ", Address, ":", Port, " failed, error ", GetLastError());
      SocketClose(socket); // Close the socket in case of a connection failure
      lastErrorTime++;
      return;
     }

// Send GET request to the server
   if(HTTPSend(socket, "GET /mt5client HTTP/1.1\r\nHost: localhost:5000\r\nUser-Agent: MT5\r\n\r\n"))
     {
      // Read the response
      string response = HTTPRecv(socket, 1000);
      if(response == "")
        {
         // Lag or error occurred, handle appropriately
         //Print("Lag... ", GetLastError());
        }
      else
        {
         // Response received, process the data
         Parse(response);
         lastErrorTime = 0;
        }
     }
   else
     {
      Print("Failed to send GET request, error ", GetLastError());
     }

// Close the socket after processing the response
   SocketClose(socket);
  }
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
