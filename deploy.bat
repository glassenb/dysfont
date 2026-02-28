@echo off
echo === VoDy Font Deploy ===
echo.
echo Deploying www/ to Cloudflare Pages (vodyfont)...
echo.
npx wrangler pages deploy www --project-name vodyfont --branch main --commit-dirty=true
echo.
echo Done. Live at:
echo   https://vodyfont.pages.dev
echo   https://vodyfont.brainpowertools.com
echo.
pause
