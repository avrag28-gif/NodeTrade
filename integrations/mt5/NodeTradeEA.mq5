#property strict
#property version   "0.2.0"
#property description "NodeTrade MT5 bridge: authenticated market-data transport, reconciliation and controlled execution."

#include <Trade/Trade.mqh>

input string InpServerOrigin = "https://YOUR-NODETRADE-SERVER";
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
string g_session_token = "";
string g_last_signal_key = "";
string g_last_event_key = "";
double g_day_start_equity = 0.0;
datetime g_day_marker = 0;

string JsonEscape(const string value)
{
   string s = value;
   StringReplace(s, "\\", "\\\\");
   StringReplace(s, "\"", "\\\"");
   return s;
}

string JsonNumber(const double value) { return DoubleToString(value, 10); }

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
      if((c >= '0' && c <= '9') || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E') e++;
      else break;
   }
   if(e <= p) return fallback;
   return StringToDouble(StringSubstr(json, p, e - p));
}

bool HttpPost(const string path, const string payload, const bool authenticated, string &response)
{
   char data[], result[];
   string result_headers = "";
   string headers = "Content-Type: application/json\r\nAccept: application/json\r\n";
   if(authenticated && g_session_token != "") headers += "Authorization: Bearer " + g_session_token + "\r\n";

   int copied = StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);
   if(copied <= 1) return false;
   copied--;
   ResetLastError();
   int status = WebRequest("POST", InpServerOrigin + path, headers, InpHTTPTimeoutMs, data, copied, result, result_headers);
   if(status == -1)
   {
      PrintFormat("NodeTrade WebRequest failed path=%s error=%d", path, GetLastError());
      return false;
   }
   response = CharArrayToString(result, 0, -1, CP_UTF8);
   if(status < 200 || status >= 300)
   {
      PrintFormat("NodeTrade HTTP status=%d path=%s response=%s", status, path, response);
      return false;
   }
   return true;
}

bool Activate()
{
   string body = "{\"account_id\":\"" + JsonEscape(InpAccountID) + "\",\"activation_key\":\"" + JsonEscape(InpActivationCode) + "\"}";
   string response;
   if(!HttpPost("/v1/activate", body, false, response)) return false;
   g_session_token = ExtractJsonString(response, "token");
   if(g_session_token == "") return false;
   Print("NodeTrade: activation successful");
   return true;
}

bool IsNewBar(const MqlRates &rates[])
{
   if(ArraySize(rates) < 1) return false;
   if(rates[0].time == g_last_bar) return false;
   g_last_bar = rates[0].time;
   return true;
}

void RefreshDayStart()
{
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   datetime marker = StructToTime(now) - now.hour * 3600 - now.min * 60 - now.sec;
   if(marker != g_day_marker)
   {
      g_day_marker = marker;
      g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   }
   if(g_day_start_equity <= 0.0) g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
}

string BuildAnalyzeRequest(const MqlRates &rates[], const MqlTick &tick)
{
   string body = "{\"account_id\":\"" + JsonEscape(InpAccountID) +
                 "\",\"symbol\":\"" + JsonEscape(_Symbol) +
                 "\",\"bid\":" + JsonNumber(tick.bid) +
                 ",\"ask\":" + JsonNumber(tick.ask) +
                 ",\"equity\":" + JsonNumber(AccountInfoDouble(ACCOUNT_EQUITY)) +
                 ",\"day_start_equity\":" + JsonNumber(g_day_start_equity) +
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
   return body + "]}";
}

bool HasOurPosition(const ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
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
   return v >= minv ? NormalizeDouble(v, 8) : 0.0;
}

bool ExecuteSignal(const string action, const double volume, const double stop, const double target, const string signal_key)
{
   if(!InpLiveTrading || action == "wait") return true;
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
   else return true;

   uint rc = trade.ResultRetcode();
   if(!sent || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_DONE_PARTIAL && rc != TRADE_RETCODE_PLACED))
   {
      PrintFormat("NodeTrade order rejected retcode=%u description=%s", rc, trade.ResultRetcodeDescription());
      return false;
   }
   g_last_signal_key = signal_key;
   return true;
}

bool SendTradeEvent(const MqlTradeTransaction &trans, const MqlTradeResult &result)
{
   if(g_session_token == "" || trans.symbol != _Symbol) return false;
   long stamp = (long)TimeCurrent();
   string event_key = IntegerToString((long)trans.deal) + ":" + IntegerToString((long)trans.order) + ":" + IntegerToString((int)trans.type) + ":" + IntegerToString(stamp);
   if(event_key == g_last_event_key) return true;
   g_last_event_key = event_key;
   string body = "{\"account_id\":\"" + JsonEscape(InpAccountID) +
                 "\",\"event_id\":\"" + JsonEscape(event_key) +
                 "\",\"symbol\":\"" + JsonEscape(trans.symbol) +
                 "\",\"event_type\":\"" + IntegerToString((int)trans.type) +
                 "\",\"ticket\":" + IntegerToString((long)trans.position) +
                 ",\"deal\":" + IntegerToString((long)trans.deal) +
                 ",\"order\":" + IntegerToString((long)trans.order) +
                 ",\"volume\":" + JsonNumber(trans.volume) +
                 ",\"price\":" + JsonNumber(trans.price) +
                 ",\"profit\":0," +
                 "\"time\":" + IntegerToString(stamp) + "}";
   string response;
   return HttpPost("/v1/trade-events", body, true, response);
}

bool Reconcile()
{
   if(g_session_token == "") return false;
   string positions = "[";
   bool first = true;
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(!first) positions += ",";
      first = false;
      positions += "{\"ticket\":" + IntegerToString((long)ticket) +
                   ",\"type\":" + IntegerToString((int)PositionGetInteger(POSITION_TYPE)) +
                   ",\"volume\":" + JsonNumber(PositionGetDouble(POSITION_VOLUME)) +
                   ",\"price\":" + JsonNumber(PositionGetDouble(POSITION_PRICE_OPEN)) + "}";
   }
   positions += "]";
   string body = "{\"account_id\":\"" + JsonEscape(InpAccountID) +
                 "\",\"symbol\":\"" + JsonEscape(_Symbol) +
                 "\",\"positions\":" + positions +
                 ",\"equity\":" + JsonNumber(AccountInfoDouble(ACCOUNT_EQUITY)) +
                 ",\"terminal_time\":" + IntegerToString((long)TimeCurrent()) + "}";
   string response;
   if(!HttpPost("/v1/reconcile", body, true, response)) return false;
   return ExtractJsonString(response, "safe_to_trade") != "false";
}

void PollNodeTrade()
{
   RefreshDayStart();
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpBars, rates);
   if(copied < 100) return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick) || tick.bid <= 0.0 || tick.ask <= 0.0 || tick.ask < tick.bid) return;
   if(!IsNewBar(rates)) return;

   string response;
   if(!HttpPost("/v1/analyze", BuildAnalyzeRequest(rates, tick), true, response)) return;
   string action = ExtractJsonString(response, "action");
   double stop = ExtractJsonNumber(response, "stop", 0.0);
   double target = ExtractJsonNumber(response, "target", 0.0);
   string request_id = ExtractJsonString(response, "request_id");
   PrintFormat("NodeTrade signal symbol=%s action=%s stop=%.5f target=%.5f request=%s", _Symbol, action, stop, target, request_id);
   if(action == "long" || action == "short") ExecuteSignal(action, InpMaxVolume, stop, target, request_id);
}

int OnInit()
{
   if(InpServerOrigin == "" || InpAccountID == "" || InpActivationCode == "") return INIT_PARAMETERS_INCORRECT;
   if(!Activate()) return INIT_FAILED;
   if(!Reconcile()) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic);
   EventSetTimer(MathMax(1, InpTimerSeconds));
   Print("NodeTrade EA initialized. Add the server origin to MT5 WebRequest allowed URLs.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { EventKillTimer(); }
void OnTimer() { PollNodeTrade(); }
void OnTick() {}

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.symbol != _Symbol) return;
   PrintFormat("NodeTrade trade transaction type=%d order=%I64u deal=%I64u retcode=%u", trans.type, trans.order, trans.deal, result.retcode);
   SendTradeEvent(trans, result);
}
