//+------------------------------------------------------------------+
//| FVG_Learning_EA.mq5                                              |
//| MQL5 Expert Advisor: FVG/IFVG detection + simple online learner  |
//| Learner: online logistic-style weight updates based on simulated |
//| trade outcomes (scan-forward on historical bars).                |
//+------------------------------------------------------------------+
#property copyright "You"
#property version   "1.0"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//======================== Inputs ================================//
input string InpSymbols           = "BTCUSD,XAUUSD,US100"; // comma-separated broker symbols
input double InpLot               = 0.10;                  // fixed lot size
input int    InpScanEveryMs       = 2000;                  // scan cadence ms
input int    InpSMA_M15           = 50;                   // trend SMA on M15

// FVG execution params
input double InpRR                = 2.0;                  // Risk:Reward
input double InpBufferPoints      = 50.0;                 // SL buffer (points)
input int    InpMaxSpreadPoints   = 200;                  // max spread allowed
input bool   InpOneTradePerSymbol = true;                 // single active trade per symbol
input bool   InpEnableTrading     = false;                // allow real orders

// Learner inputs
input bool   InpModelEnabled      = true;                 // use model to filter trades
input bool   InpModelLearn        = true;                 // update model from simulated results
input double InpModelLR           = 0.01;                 // learning rate
input double InpModelThreshold    = 0.55;                 // threshold to accept trades
input int    InpModelMinSamples   = 8;                    // min samples before vetoing
input string InpModelFile         = "fvg_model.dat";    // file in MQL5/Files
input int    InpSimLookaheadBars  = 300;                  // bars to scan-forward to decide win/lose

//======================== Types/Globals ========================//
#define FEATURE_COUNT 6

typedef struct Sample
{
   double features[FEATURE_COUNT];
};

double g_weights[FEATURE_COUNT];
double g_bias = 0.0;
int    g_samples_count = 0;

string gSymbols[];
ulong  gLastScanMs = 0;

// temporary storage for simulated training (for visibility)
int    g_log_index = 0;

//======================== Utilities ============================//
void SplitSymbols(const string csv)
{
   ArrayResize(gSymbols,0);
   int cnt = StringSplit(csv,',',gSymbols);
   for(int i=0;i<cnt;i++){
      StringTrimLeft(gSymbols[i]);
      StringTrimRight(gSymbols[i]);
   }
}

bool EnsureSymbol(const string sym)
{
   if(!SymbolSelect(sym,true)){
      PrintFormat("[WARN] Could not select symbol %s", sym);
      return(false);
   }
   return(true);
}

bool IsSpreadOK(const string sym)
{
   MqlTick t;
   if(!SymbolInfoTick(sym,t)) return(false);
   double pt = SymbolInfoDouble(sym,SYMBOL_POINT);
   int spread_pts = (int)MathRound((t.ask - t.bid)/pt);
   return(spread_pts <= InpMaxSpreadPoints);
}

// Sigmoid
double Sigmoid(double x)
{
   return(1.0/(1.0+MathExp(-x)));
}

// Predict probability
double ModelPredict(const double &x[])
{
   double s=0.0;
   for(int i=0;i<FEATURE_COUNT;i++) s += g_weights[i]*x[i];
   s += g_bias;
   return Sigmoid(s);
}

// Online update weights (logistic SGD)
void ModelUpdate(const double &x[], int y)
{
   double p = ModelPredict(x);
   double error = (double)y - p;
   for(int i=0;i<FEATURE_COUNT;i++) g_weights[i] += InpModelLR * error * x[i];
   g_bias += InpModelLR * error;
   g_samples_count++;
}

// Save/load model
void SaveModel()
{
   int handle = FileOpen(InpModelFile, FILE_WRITE|FILE_BIN);
   if(handle==INVALID_HANDLE){ Print("[MODEL] Save: FileOpen failed"); return; }
   for(int i=0;i<FEATURE_COUNT;i++) FileWriteDouble(handle, g_weights[i]);
   FileWriteDouble(handle, g_bias);
   FileWriteInteger(handle, g_samples_count);
   FileClose(handle);
   PrintFormat("[MODEL] Saved %d weights to %s", FEATURE_COUNT, InpModelFile);
}

void LoadModel()
{
   int handle = FileOpen(InpModelFile, FILE_READ|FILE_BIN);
   if(handle==INVALID_HANDLE){ Print("[MODEL] Load: no file, starting fresh"); return; }
   for(int i=0;i<FEATURE_COUNT;i++) g_weights[i] = FileReadDouble(handle);
   g_bias = FileReadDouble(handle);
   g_samples_count = (int)FileReadInteger(handle);
   FileClose(handle);
   PrintFormat("[MODEL] Loaded model samples=%d", g_samples_count);
}

// Normalize helper (avoid div by zero)
double SafeNorm(double v, double base)
{
   if(base==0) return(0);
   return(v/base);
}

//======================== FVG detection ========================//
// CopyRates wrapper
bool GetRates(const string sym, ENUM_TIMEFRAMES tf, int bars, MqlRates &rates[])
{
   ArraySetAsSeries(rates,true);
   int copied = CopyRates(sym, tf, 0, bars, rates);
   return(copied>0);
}

// Find 3-candle FVGs on rates[]
int FindFVGs(const MqlRates &rates[], int size, string &types[], double &lows[], double &highs[], double &mids[])
{
   int found=0;
   for(int i=2;i<size;i++){
      // bullish
      if(rates[i+0].high < rates[i-2].low){} // placeholder to avoid out-of-range in some builds
      if(rates[i-2].high < rates[i].low){
         types[found] = "bull";
         lows[found] = rates[i-2].high;
         highs[found] = rates[i].low;
         mids[found] = (lows[found]+highs[found])/2.0;
         found++;
      }
      // bearish
      if(rates[i-2].low > rates[i].high){
         types[found] = "bear";
         lows[found] = rates[i].high;
         highs[found] = rates[i-2].low;
         mids[found] = (lows[found]+highs[found])/2.0;
         found++;
      }
      if(found>=100) break;
   }
   return(found);
}

//======================== Feature engineering ===================//
// Build feature vector of length FEATURE_COUNT
void BuildFeatures(const string sym, int tf_index, double fvg_size, double spread_pts, double recent_vol, double &out[])
{
   // Feature mapping (simple):
   // 0: trend (M15): +1 up, -1 down
   // 1: fvg_size_norm
   // 2: tf_index_norm (0..1)
   // 3: spread_norm
   // 4: time_bucket (0..1)
   // 5: recent_vol_norm

   // compute trend
   MqlRates m15[]; if(!GetRates(sym, PERIOD_M15, 200, m15)){
      for(int i=0;i<FEATURE_COUNT;i++) out[i]=0.0; return;
   }
   double closeArr[]; ArrayResize(closeArr, ArraySize(m15));
   for(int i=0;i<ArraySize(m15);i++) closeArr[i] = m15[i].close;
   // SMA
   double sum=0.0; int N = InpSMA_M15; if(N<=0) N=50;
   for(int i=0;i<N && i<ArraySize(m15); i++) sum += closeArr[i];
   double sma = sum / MathMax(1, N);
   double trend = (closeArr[0] > sma) ? 1.0 : -1.0;

   double fvg_norm = SafeNorm(fvg_size, closeArr[0]);
   double tf_norm = SafeNorm(tf_index, 2.0); // tf_index 0..2
   double spread_norm = SafeNorm(spread_pts, 200.0);
   double time_bucket = 0.0;
   // time bucket: NY session roughly 13:00-21:00 server time approx; simplify: use hour
   datetime now = TimeCurrent();
   int hr = TimeHour(now);
   if(hr>=13 && hr<=21) time_bucket = 1.0; else time_bucket = 0.0;
   double vol_norm = SafeNorm(recent_vol, 1000.0);

   out[0] = trend;
   out[1] = fvg_norm;
   out[2] = tf_norm;
   out[3] = spread_norm;
   out[4] = time_bucket;
   out[5] = vol_norm;
}

//======================== Simulate trade outcome ===================//
// Scan-forward on provided rates[] to see which level is hit first
int SimulateOutcome(const MqlRates &rates[], int size, double entry_price, double sl, double tp, int lookahead)
{
   int max_i = MathMin(size-1, lookahead);
   for(int i=0;i<=max_i;i++){
      double high = rates[i].high;
      double low  = rates[i].low;
      // if high touches tp first
      if(high>=tp && low<=sl){
         // both hit within same bar; which closer?
         double dist_tp = MathAbs(tp - entry_price);
         double dist_sl = MathAbs(entry_price - sl);
         return (dist_tp<=dist_sl) ? 1 : 0; // prefer tp
      }
      if(high>=tp) return 1;
      if(low<=sl)  return 0;
   }
   // neither hit within lookahead -> consider loss (conservative)
   return 0;
}

//======================== Decision & scan =========================
void EvaluateSymbol(const string sym)
{
   if(!EnsureSymbol(sym)) return;
   if(!IsSpreadOK(sym)) { PrintFormat("[SKIP] %s spread too high", sym); return; }

   // Load recent ticks for mid/spread
   MqlTick tk; if(!SymbolInfoTick(sym, tk)) return;
   double mid = (tk.ask + tk.bid)/2.0;
   double pt = SymbolInfoDouble(sym, SYMBOL_POINT);
   double spread_pts = (tk.ask - tk.bid)/pt;

   // Get rates for M1 and M5 and M15
   MqlRates r1[]; if(!GetRates(sym, PERIOD_M1, 800, r1)) return;
   MqlRates r5[]; if(!GetRates(sym, PERIOD_M5, 800, r5)) return;
   MqlRates r15[]; if(!GetRates(sym, PERIOD_M15, 800, r15)) return;

   // Find FVGs (M1 first, then M5, then M15)
   string types[200]; double lows[200]; double highs[200]; double mids[200];
   int f1 = FindFVGs(r1, ArraySize(r1), types, lows, highs, mids);
   int f5 = FindFVGs(r5, ArraySize(r5), types, lows, highs, mids);
   int f15 = FindFVGs(r15, ArraySize(r15), types, lows, highs, mids);

   // helper to process array of FVGs found
   int i;
   for(i=f1-1;i>=0;i--){
      double low = lows[i]; double high = highs[i]; string tppe = types[i];
      if(!(mid>=low && mid<=high)) continue; // price must be inside gap
      // trend filter
      double features[FEATURE_COUNT]; BuildFeatures(sym,0, high-low, spread_pts, r1[0].tick_volume, features);
      double p = ModelPredict(features);
      bool allow = (!InpModelEnabled) || (g_samples_count < InpModelMinSamples) || (p>=InpModelThreshold);
      double sl, tptarget;
      if(tppe=="bull"){
         sl = low - InpBufferPoints*pt;
         double risk = mid - sl; if(risk<=0) continue;
         tptarget = mid + InpRR * risk;
         if(allow){
            if(InpEnableTrading){ PlaceMarket(sym, ORDER_TYPE_BUY, sl, tptarget); }
            else PrintFormat("[SIGNAL BUY %s] p=%.3f allow=%d sl=%.5f tp=%.5f", sym, p, (int)allow, sl, tptarget);
         }
         // Simulate outcome on M1 forward bars
         int outcome = SimulateOutcome(r1, ArraySize(r1), mid, sl, tptarget, InpSimLookaheadBars);
         if(InpModelLearn){ ModelUpdate(features, outcome); SaveModel(); }
         return;
      }
      else{
         sl = high + InpBufferPoints*pt;
         double risk = sl - mid; if(risk<=0) continue;
         tptarget = mid - InpRR * risk;
         if(allow){
            if(InpEnableTrading){ PlaceMarket(sym, ORDER_TYPE_SELL, sl, tptarget); }
            else PrintFormat("[SIGNAL SELL %s] p=%.3f allow=%d sl=%.5f tp=%.5f", sym, p, (int)allow, sl, tptarget);
         }
         int outcome = SimulateOutcome(r1, ArraySize(r1), mid, sl, tptarget, InpSimLookaheadBars);
         if(InpModelLearn){ ModelUpdate(features, outcome); SaveModel(); }
         return;
      }
   }
   // M5
   for(i=f1;i<f1+f5;i++){
      int idx = i; if(idx<0) continue;
      double low = lows[idx]; double high = highs[idx]; string tppe = types[idx];
      if(!(mid>=low && mid<=high)) continue;
      double features[FEATURE_COUNT]; BuildFeatures(sym,1, high-low, spread_pts, r5[0].tick_volume, features);
      double p = ModelPredict(features);
      bool allow = (!InpModelEnabled) || (g_samples_count < InpModelMinSamples) || (p>=InpModelThreshold);
      double sl, tptarget;
      if(tppe=="bull"){
         sl = low - InpBufferPoints*pt;
         double risk = mid - sl; if(risk<=0) continue;
         tptarget = mid + InpRR * risk;
         if(allow){ if(InpEnableTrading){ PlaceMarket(sym, ORDER_TYPE_BUY, sl, tptarget); } else PrintFormat("[SIGNAL BUY %s] p=%.3f allow=%d", sym, p, (int)allow); }
         int outcome = SimulateOutcome(r5, ArraySize(r5), mid, sl, tptarget, InpSimLookaheadBars);
         if(InpModelLearn){ ModelUpdate(features, outcome); SaveModel(); }
         return;
      } else {
         sl = high + InpBufferPoints*pt;
         double risk = sl - mid; if(risk<=0) continue;
         tptarget = mid - InpRR * risk;
         if(allow){ if(InpEnableTrading){ PlaceMarket(sym, ORDER_TYPE_SELL, sl, tptarget); } else PrintFormat("[SIGNAL SELL %s] p=%.3f allow=%d", sym, p, (int)allow); }
         int outcome = SimulateOutcome(r5, ArraySize(r5), mid, sl, tptarget, InpSimLookaheadBars);
         if(InpModelLearn){ ModelUpdate(features, outcome); SaveModel(); }
         return;
      }
   }
   // M15
   for(i=f1+f5;i<f1+f5+f15;i++){
      int idx = i; if(idx<0) continue;
      double low = lows[idx]; double high = highs[idx]; string tppe = types[idx];
      if(!(mid>=low && mid<=high)) continue;
      double features[FEATURE_COUNT]; BuildFeatures(sym,2, high-low, spread_pts, r15[0].tick_volume, features);
      double p = ModelPredict(features);
      bool allow = (!InpModelEnabled) || (g_samples_count < InpModelMinSamples) || (p>=InpModelThreshold);
      double sl, tptarget;
      if(tppe=="bull"){
         sl = low - InpBufferPoints*pt;
         double risk = mid - sl; if(risk<=0) continue;
         tptarget = mid + InpRR * risk;
         if(allow){ if(InpEnableTrading){ PlaceMarket(sym, ORDER_TYPE_BUY, sl, tptarget); } else PrintFormat("[SIGNAL BUY %s] p=%.3f allow=%d", sym, p, (int)allow); }
         int outcome = SimulateOutcome(r15, ArraySize(r15), mid, sl, tptarget, InpSimLookaheadBars);
         if(InpModelLearn){ ModelUpdate(features, outcome); SaveModel(); }
         return;
      } else {
         sl = high + InpBufferPoints*pt;
         double risk = sl - mid; if(risk<=0) continue;
         tptarget = mid - InpRR * risk;
         if(allow){ if(InpEnableTrading){ PlaceMarket(sym, ORDER_TYPE_SELL, sl, tptarget); } else PrintFormat("[SIGNAL SELL %s] p=%.3f allow=%d", sym, p, (int)allow); }
         int outcome = SimulateOutcome(r15, ArraySize(r15), mid, sl, tptarget, InpSimLookaheadBars);
         if(InpModelLearn){ ModelUpdate(features, outcome); SaveModel(); }
         return;
      }
   }
}

// Place market order wrapper
bool PlaceMarket(const string sym, ENUM_ORDER_TYPE type, double sl, double tp)
{
   if(!EnsureSymbol(sym)) return false;
   double price = (type==ORDER_TYPE_BUY) ? SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);
   trade.SetExpertMagicNumber(20250823);
   trade.SetDeviationInPoints(20);
   bool ok=false;
   if(type==ORDER_TYPE_BUY) ok = trade.Buy(InpLot, sym, price, sl, tp, "fvg-learner");
   else ok = trade.Sell(InpLot, sym, price, sl, tp, "fvg-learner");
   if(!ok) PrintFormat("[ORDER FAIL] %s err=%d", sym, GetLastError());
   return ok;
}

//======================== MT5 events ============================//
int OnInit()
{
   SplitSymbols(InpSymbols);
   // initialize weights to small random or zero
   for(int i=0;i<FEATURE_COUNT;i++) g_weights[i] = 0.0;
   g_bias = 0.0;
   LoadModel();
   PrintFormat("FVG_Learning_EA initialized. Symbols: %s", InpSymbols);
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   SaveModel();
   EventKillTimer();
}

void OnTimer()
{
   // nothing here; keep EA alive
}

void OnTick()
{
   // cadence check
   ulong nowms = GetMicrosecondCount()/1000;
   if(nowms - gLastScanMs < (ulong)InpScanEveryMs) return;
   gLastScanMs = nowms;

   for(int i=0;i<ArraySize(gSymbols);i++){
      string s = gSymbols[i];
      if(StringLen(s)==0) continue;
      EvaluateSymbol(s);
   }
}

//+------------------------------------------------------------------+
// End of file
//+------------------------------------------------------------------+