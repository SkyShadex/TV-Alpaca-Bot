//+------------------------------------------------------------------+
//|                                                    SkyBot_TV.mq5 |
//|                                                        SkyShadex |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#include<Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
CTrade trade;
CSymbolInfo syminfo;
#property script_show_inputs

input string   Address = "localhost";
input int      Port = 5000;
input int      Pyramid = 5;
input double   Risk = 5;
input double   Reward = 3;
input double   Max_Lot = 1.63;
input double   StopLossPoints = 6;
datetime previousDateTime = 0;
bool         ExtTLS =false;


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
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
//--- destroy the timer after completing the work
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
   return(error);
  }
//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnTimer()
  {
   serverClock();
   socketSystem();
  }

//+------------------------------------------------------------------+;

//+------------------------------------------------------------------+
//|                                                                  |
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
   if(!SocketConnect(socket, Address, Port, 500))
     {
      Print("Connection to ", Address, ":", Port, " failed, error ", GetLastError());
      SocketClose(socket); // Close the socket in case of a connection failure
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

   string symCheck = _Symbol;

   string symbolPrefix = StringSubstr(symbol, 0, 4);
   string _SymbolPrefix = StringSubstr(_Symbol, 0, 4);
//Print(symbolPrefix,_SymbolPrefix);

   if(dateTime != previousDateTime && symbolPrefix == _SymbolPrefix)
     {
      // Print the extracted variables
      Print("");
      Print("");
      Print("New Order Found! ", side, "Price:", DoubleToString(price));
      pushOrder(side, price);
     }
   previousDateTime = dateTime;
  }



//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void pushOrder(string side,double price)
  {
   price = NormalizeDouble(price,_Digits);
   if(_Symbol=="XRPUSD")
     {
      price = syminfo.NormalizePrice(price/100);
     }
   double ticksize = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double ask = SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread = MathAbs(ask-bid);
   double source = ask;
//double priceWithinDeviation = (price > ask*1.1 || price < ask*0.9 ) ? ask : price;  // Replace invalid price with ask price within deviation
   double newprice = MathMax(source,price);
   double sl = newprice - StopLossPoints * ticksize;
   sl = syminfo.NormalizePrice(sl-spread);
   double slDistance = newprice - sl;
   double tp = syminfo.NormalizePrice(newprice + MathAbs(slDistance*Reward));
   double lots = calcLots(slDistance);
//if(sl < 0){
//   sl = MathAbs(sl);
//}
   Print(_Symbol," [Order Payload]: ","Ask: ",ask,", Bid: ",bid,", Spread: ",spread,", Price: ",price," ===================================>");
   Print(_Symbol," [Order Payload]: ","New Price: ",newprice,", SL: ",sl," TP: ",tp,", Lots: ",lots," ===================================>");
   if(StringFind(side, "buy") >= 0)
     {
      trade.BuyLimit(lots,ask,_Symbol,sl,tp,ORDER_TIME_GTC,0,NULL);
      Print("Order Placed");
     }
   if(StringFind(side, "sell") >= 0)
     {
      CloseAllPositions();
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CloseAllPositions()
  {
   bool positionsClosed = false;
   bool ordersClosed = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetString(POSITION_SYMBOL) == _Symbol)
        {
         trade.PositionClose(ticket);
         positionsClosed = true;
        }
     }
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
   if(positionsClosed || ordersClosed)
     {
      Print("Closing Positions");
     }
   else
     {
      Print("No Open Positions Found");
     }
  }



//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double calcLots(double slDistance)
  {
   double sld = slDistance;
   double ticksize = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double tickvalue = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double lotstep = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);

   if(ticksize == 0 || tickvalue == 0 || lotstep == 0)
     {
      Print(__FUNCTION__,1," > Lotsize cannot be calculated...");
      return 0;
     }

   double riskMoney = AccountInfoDouble(ACCOUNT_MARGIN_FREE)*(Risk/100);
   Print("RISK: ",riskMoney, "===================================>");
   double moneyPerLotStep = (sld / ticksize) * tickvalue * lotstep;

   if(moneyPerLotStep == 0)
     {
      Print(__FUNCTION__,2," > Lotsize cannot be calculated...");
      return 0;
     }
   double lots = MathFloor(Risk / moneyPerLotStep) * lotstep;
//Print(lots);
   double minvolume = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxvolume = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);

   if(maxvolume!=0)
      lots = MathMin(lots,maxvolume);
   if(minvolume!=0)
      lots = MathMax(lots,minvolume);
//lots = lots * Risk/10;
//Print(lots);
   lots = NormalizeDouble(lots,2);
//Print(lots);
   return lots;
  }
//+------------------------------------------------------------------+
