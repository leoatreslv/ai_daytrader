# Task: Trading Enhancements and Bug Fixes

- [x] Analyze `main.py` and `config.py` for current position limit implementation <!-- id: 0 -->
- [x] Implement robust position limit check in `main.py` <!-- id: 1 -->
- [x] Investigate why TP/SL orders aren't executing as expected <!-- id: 2 -->
- [x] Update TP/SL logic to use `PositionID` for Hedging accounts <!-- id: 3 -->
- [x] Implement Stop Loss and Take Profit as linked protections or Closing orders <!-- id: 4 -->
- [x] Verify both fixes in a demo environment <!-- id: 5 -->
- [x] Improve Fill Price extraction in ExecutionReport (check Tag 6) <!-- id: 6 -->
- [x] Fix Market Price fallback logic (handle direct ID matching) <!-- id: 7 -->
- [x] Verify PnL calculation works for Market Orders <!-- id: 8 -->
- [x] Add `TIMEZONE_OFFSET` to `config.py` <!-- id: 9 -->
- [x] Fix `get_current_session_start` date calculation lag in `ctrader_fix_client.py` <!-- id: 10 -->
- [x] Verify `/report` shows the correct session start date <!-- id: 11 -->
- [x] Register `/report` command in Telegram Bot Menu <!-- id: 12 -->
- [x] Push all fixes and verification tools to GitHub <!-- id: 13 -->
