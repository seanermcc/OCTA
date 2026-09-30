@echo off
call D:\Programs\Anaconda\Scripts\activate.bat octa
set PYTHONDONTWRITEBYTECODE=1
cd /d G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_unet_v6\review
python -B viewer.py --review-directory G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_unet_v6\review\demo_this_computer
