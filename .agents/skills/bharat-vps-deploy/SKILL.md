---
name: bharat-vps-deploy
description: Autonomous VPS deployment & health check protocol across Zerodha (9007), Kotak (9003), and HDFC (9004).
---

# 🚀 BHARAT VPS DEPLOYMENT & HEALTH CHECK PROTOCOL

## 1. Deployment Execution Pipeline
Always follow Gurjas's Single-Brick Lego Protocol:
```
[1. DIAGNOSE] ➔ [2. BLUEPRINT] ➔ [3. APPROVAL] ➔ [4. SINGLE-BRICK CODE] ➔ [5. DUAL-SERVICE DEPLOY] ➔ [6. VERIFY]
```

## 2. Deployment Sequence
1. **Local Pre-Check**: Ensure all modified python files compile without syntax errors (`py_compile.compile`).
2. **SFTP Sync**: Upload updated files to remote VPS directory (`/root/BHARAT-SYSTEMS/ZERODHA-OS/`).
3. **Bytecode Purge**: Delete all `.pyc` files and `__pycache__` directories to prevent serving stale RAM cache.
4. **Dual-Service Restart**:
   - Engine: `systemctl restart zerodha_engine.service`
   - Dashboard: `systemctl restart zerodha_dashboard.service`
5. **Post-Deploy Health Check**:
   - `systemctl is-active zerodha_engine.service zerodha_dashboard.service`
   - Check Streamlit Port 9007 status.
   - Verify broker positions (`kite.positions()['net']`) remain 100% untouched and intact.
