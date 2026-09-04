#property strict
#property version   "0.1.0"
#property description "NodeTrade MT5 bridge: authenticated market-data transport and optional execution."

#include <Trade/Trade.mqh>

input string InpServerURL = "https://YOUR-NODETRADE-SERVER/v1/analyze";
input string InpAccountID = "";
input string InpActivationCode = "";
input int    InpBars = 300;
input int    InpTimerSeconds = 5;
input int    InpHTTPTimeoutMs = 5000;
input bool   InpLiveTrading = false;
input double InpMaxVolume = 0.10;
input ulong  InpMagic = 26090401;
input bool   InpAllowLong = true;
input bool   InpAllowShort = true;

CTrade trade;
datetime g_last_bar = 0;
string   g_last_signal_key = "";

string JsonEscape(const string value)
{
   string s = value;
   StringReplace(s, "\\", "\\\\");
   StringReplace(s, "\"", "\\\"");
   return s;
}

string JsonNumber(const double value)
{
   return DoubleToString(value, 10);
}

string ExtractJsonString(const string json, const string key)
{
   string needle = "\"" + key + "\":\"";
   int p = StringFind(json, needle);
   if(p < 0) return "";
   p += StringLen(needle);
   int e = StringFind(json, "\"", p);
   if(e < 0) return "";
   return StringSubstr(json, p, e - p);
}

double ExtractJsonNumber(const string json, const string key, const double fallback = 0.0)
{
   string needle = "\"" + key + "\":";
   int p = StringFind(json, needle);
   if(p < 0) return fallback;
   p += StringLen(needle);
   int e = p;
   int n = StringLen(json);
   while(e < n)
   {
      ushort c = StringGetCharacter(json, e);
      if((c >= '0' && c <= '9') || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E')
         e++;
      else
         break;
   }
   if(e <= p) return fallback;
   return StringToDouble(StringSubstr(json, p, e - p));
}

bool IsNewBar(const MqlRates &rates[])
{
   if(ArraySize(rates) < 1) return false;
   datetime current = rates[0].time;
   if(current == g_last_bar) return false;
   g_last_bar = current;
   return true;
}

string BuildRequest(const MqlRates &rates[], const MqlTick &tick)
{
   string body = "{\"account_id\":\"" + JsonEscape(InpAccountID) +
                 "\",\"activation_key\":\"" + JsonEscape(InpActivationCode) +
                 "\",\"symbol\":\"" + JsonEscape(_Symbol) +
                 "\",\"bid\":" + JsonNumber(tick.bid) +
                 ",\"ask\":" + JsonNumber(tick.ask) +
                 ",\"equity\":" + JsonNumber(AccountInfoDouble(ACCOUNT_EQUITY)) +
                 ",\"day_start_equity\":" + JsonNumber(AccountInfoDouble(ACCOUNT_EQUITY)) +
                 ",\"candles\":[";

   int total = ArraySize(rates);
   for(int i = total - 1; i >= 0; --i)
   {
      if(i < total - 1) body += ",";
      body += "{\"time\":" + IntegerToString((long)rates[i].time) +
              ",\"open\":" + JsonNumber(rates[i].open) +
              ",\"high\":" + JsonNumber(rates[i].high) +
              ",\"low\":" + JsonNumber(rates[i].low) +
              ",\"close\":" + JsonNumber(rates[i].close) +
              ",\"volume\":" + JsonNumber((double)rates[i].tick_volume) + "}";
   }
   body += "]}";
   return body;
}

bool RequestSignal(const string payload, string &response)
{
   char data[];
   char result[];
   string result_headers = "";
   string headers = "Content-Type: application/json\r\nAccept: application/json\r\n";

   int copied = StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);
   if(copied <= 0) return false;
   copied--; // exclude terminating NUL

   ResetLastError();
   int status = WebRequest("POST", InpServerURL, headers, InpHTTPTimeoutMs, data, copied, result, result_headers);
   if(status == -1)
   {
      PrintFormat("NodeTrade WebRequest failed. error=%d", GetLastError());
      return false;
   }
   response = CharArrayToString(result, 0, -1, CP_UTF8);
   if(status < 200 || status >= 300)
   {
      PrintFormat("NodeTrade server HTTP status=%d response=%s", status, response);
      return false;
   }
   return true;
}

bool HasOurPosition(const ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type) return true;
   }
   return false;
}

double NormalizeVolume(const double requested)
{
   double minv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxv = MathMin(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), InpMaxVolume);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0 || maxv < minv) return 0.0;
   double v = MathMax(minv, MathMin(maxv, requested));
   v = MathFloor(v / step + 1e-9) * step;
   if(v < minv) return 0.0;
   return NormalizeDouble(v, 8);
}

bool ExecuteSignal(const string action, const double volume, const double stop, const double target, const string signal_key)
{
   if(!InpLiveTrading) return true;
   if(signal_key == "" || signal_key == g_last_signal_key) return true;

   double v = NormalizeVolume(volume);
   if(v <= 0.0) return false;

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetAsyncMode(false);

   bool sent = false;
   if(action == "long" && InpAllowLong && !HasOurPosition(POSITION_TYPE_BUY))
      sent = trade.Buy(v, _Symbol, 0.0, stop, target, "NodeTrade");
   else if(action == "short" && InpAllowShort && !HasOurPosition(POSITION_TYPE_SELL))
      sent = trade.Sell(v, _Symbol, 0.0, stop, target, "NodeTrade");
   else if(action == "wait")
      return true;

   if(!sent)
   {
      PrintFormat("NodeTrade order request failed: retcode=%u description=%s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      return false;
   }

   // A true CTrade return value only means the request passed local checks.
   // Always inspect the trade-server retcode before considering the order accepted.
   uint rc = trade.ResultRetcode();
   if(rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_DONE_PARTIAL && rc != TRADE_RETCODE_PLACED)
   {
      PrintFormat("NodeTrade trade-server rejection: retcode=%u description=%s", rc, trade.ResultRetcodeDescription());
      return false;
   }

   g_last_signal_key = signal_key;
   return true;
}

void PollNodeTrade()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpBars, rates);
   if(copied < 100)
   {
      PrintFormat("NodeTrade: insufficient MT5 history, copied=%d", copied);
      return;
   }

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      PrintFormat("NodeTrade: SymbolInfoTick failed error=%d", GetLastError());
      return;
   }
   if(tick.bid <= 0.0 || tick.ask <= 0.0 || tick.ask < tick.bid) return;

   string response;
   if(!RequestSignal(BuildRequest(rates, tick), response)) return;

   string action = ExtractJsonString(response, "action");
   double confidence = ExtractJsonNumber(response, "confidence", 0.0);
   double entry = ExtractJsonNumber(response, "entry", 0.0);
   double stop = ExtractJsonNumber(response, "stop", 0.0);
   double target = ExtractJsonNumber(response, "target", 0.0);
   string request_id = ExtractJsonString(response, "request_id");

   PrintFormat("NodeTrade signal symbol=%s action=%s confidence=%.4f entry=%.5f stop=%.5f target=%.5f request=%s",
               _Symbol, action, confidence, entry, stop, target, request_id);

   // Position sizing remains server-side in NodeTrade. This EA deliberately does
   // not infer risk from confidence. A production response should add a validated
   // volume field after broker-specific sizing has been incorporated server-side.
   if(action == "long" || action == "short")
      ExecuteSignal(action, InpMaxVolume, stop, target, request_id);
}

int OnInit()
{
   if(InpServerURL == "" || InpAccountID == "" || InpActivationCode == "")
   {
      Print("NodeTrade: Server URL, Account ID and Activation Code are required.");
      return INIT_PARAMETERS_INCORRECT;
   }

   trade.SetExpertMagicNumber(InpMagic);
   EventSetTimer(MathMax(1, InpTimerSeconds));
   Print("NodeTrade EA initialized. Add the API origin to MT5 WebRequest allowed URLs before use.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   PollNodeTrade();
}

void OnTick()
{
   // Trading decisions are timer-driven to avoid sending a request on every tick.
   // This event remains intentionally lightweight.
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.symbol != _Symbol) return;
   PrintFormat("NodeTrade trade transaction type=%d order=%I64u deal=%I64u retcode=%u",
               trans.type, trans.order, trans.deal, result.retcode);
   // Production feedback endpoint should be added here so deal/position outcomes
   // are returned to NodeTrade for monitoring and post-trade diagnosis.
}
