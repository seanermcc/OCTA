from common import *
p=HERE/'gallery/app.js';s=p.read_text(encoding='utf8')
old="c.style.width=`${100*Number($('bzoom').value)}%`;"
new="let baseWidth=Math.min(c.parentElement.clientWidth,900,512*440/(depth+36));c.style.width=`${baseWidth*Number($('bzoom').value)}px`;"
assert old in s;s=s.replace(old,new);tmp=p.with_suffix('.tmp');tmp.write_text(s,encoding='utf8');os.replace(tmp,p)
p=HERE/'gallery/style.css';s=p.read_text(encoding='utf8')+'\n#bscan{margin:0 auto}\n';tmp=p.with_suffix('.tmp');tmp.write_text(s,encoding='utf8');os.replace(tmp,p)
