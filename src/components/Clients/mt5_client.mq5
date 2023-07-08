//+------------------------------------------------------------------+
//|                                                    SkyBot_TV.mq5 |
//|                                                        SkyShadex |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#include<Trade\Trade.mqh>
CTrade trade;
#property script_show_inputs
 
input string   Address = "localhost";
input int      Port = 5000;
input int      Pyramid = 5;
input double   Risk = 1;
input double   Max_Lot = 1.63;
input double   StopLossPip = 400;
bool         ExtTLS =false;




int OnInit()
  {
//--- create a timer with a 1 second period
   EventSetTimer(3);
 
//---
   return(INIT_SUCCEEDED);
   }   
void OnDeinit(const int reason)
  {
//--- destroy the timer after completing the work
   EventKillTimer();
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
      if (len)
      {
         int rsp_len;
         // Various reading commands depending on whether the connection is secure or not
         if (ExtTLS)
            rsp_len = SocketTlsRead(socket, rsp, len);
         else
            rsp_len = SocketRead(socket, rsp, len, timeout);
         // Analyze the response
         if (rsp_len > 0)
         {
            result += CharArrayToString(rsp, 0, rsp_len);
            // Check if the entire response has been received
            int header_end = StringFind(result, "\r\n\r\n");
            if (header_end > 0)
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
   while (GetTickCount() < timeout_check && !IsStopped());
   string error = "";
   return(error);
}
//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnTimer()
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
   string com=StringFormat("                  Start time: %s\r\n",TimeToString(start_time,TIME_MINUTES|TIME_SECONDS));
   com=com+StringFormat("                  Local time: %s\r\n",TimeToString(local_time,TIME_MINUTES|TIME_SECONDS));
   com=com+StringFormat("TimeTradeServer time: %s\r\n",TimeToString(trade_server_time,TIME_MINUTES|TIME_SECONDS));
   com=com+StringFormat(" EstimatedServer time: %s\r\n",TimeToString(calculated_server_time,TIME_MINUTES|TIME_SECONDS));
   //--- display values of all counters on the chart
   Comment(com);
   int socket=SocketCreate();
//--- check the handle
   if(socket!=INVALID_HANDLE)
     {
      //--- connect if all is well
      if(SocketConnect(socket,Address,Port,1000))
        {
         //Print("Established connection to ",Address,":",Port);
 
         string   subject,issuer,serial,thumbprint;
         datetime expiration;
         //--- if connection is secured by the certificate, display its data
         if(SocketTlsCertificate(socket,subject,issuer,serial,thumbprint,expiration))
           {
            Print("TLS certificate:");
            Print("   Owner:  ",subject);
            Print("   Issuer:  ",issuer);
            Print("   Number:     ",serial);
            Print("   Print: ",thumbprint);
            Print("   Expiration: ",expiration);
            ExtTLS=true;
           }
         // Send GET request to the server
         if (HTTPSend(socket, "GET /mt5client HTTP/1.1\r\nHost: localhost:5000\r\nUser-Agent: MT5\r\n\r\n"))
            {
               //Print("GET request sent...");
               //Read the response
               string response = HTTPRecv(socket, 1000);
               if (response == "")
                  Print("Lag... ", GetLastError());
               else
                  Parse(response);   
            }
         else
            Print("Failed to send GET request, error ",GetLastError());
        }
      else
        {
         Print("Connection to ",Address,":",Port," failed, error ",GetLastError());
        }
      //--- close a socket after using
      SocketClose(socket);
     }
   else{
      Print("Failed to create a socket, error ",GetLastError());
    }
   }
//+------------------------------------------------------------------+
datetime previousDateTime = 0;

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
   
   if (dateTime != previousDateTime && symbolPrefix == _SymbolPrefix){
      // Print the extracted variables
      Print("New Order Found!");
      Print("Timestamp:", dateTime);
      Print("Symbol:", symbol, _Symbol);
      Print("Side:", side);
      Print("Price:", price);
      pushOrder(side, price);
   }
   previousDateTime = dateTime;
}


void pushOrder(string side,double price)
{
   double ask = NormalizeDouble(SymbolInfoDouble(_Symbol,SYMBOL_ASK),_Digits);
   double newprice = MathMin(ask,price);
   Print(_Point);
   double sl = newprice - StopLossPip*_Point;
   double lots = calcLots(newprice - sl);
   if(sl < 0){
      sl = MathAbs(sl);
   }
   Print("Ask:",ask,", Price: ",price,", New Price: ",newprice,", SL: ",sl,", Lots: ",lots);
   if (StringFind(side, "buy") >= 0){
      trade.Buy(lots,_Symbol,newprice,sl,0,NULL);
      Print("Order Placed");
   }
   if (StringFind(side, "sell") >= 0){
      CloseAllPositions();
      Print("Closing Positions");
   }
}

void CloseAllPositions()
{
   for (int i = PositionsTotal() - 1; i >= 0; i--)
   {
      int ticket = PositionGetTicket(i);
      trade.PositionClose(ticket);
   }
}



double calcLots(double slPoints){
   double risk = AccountInfoDouble(ACCOUNT_BALANCE)*(Risk/100);
   Print("RISK",risk);
   double ticksize = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double tickvalue = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double lotstep = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   
   double moneyPerLotStep = slPoints / ticksize * tickvalue * lotstep;
   double lots = MathFloor(risk / moneyPerLotStep) * lotstep;
   Print(lots);
   double minvolume = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxvolume = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   
   if(maxvolume!=0) lots = MathMin(lots,maxvolume);
   if(minvolume!=0) lots = MathMax(lots,minvolume);
   lots = lots * Risk/10;
   Print(lots);
   lots = NormalizeDouble(lots,2);
   Print(lots);
   return lots;
}