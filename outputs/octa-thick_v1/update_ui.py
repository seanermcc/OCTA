from pathlib import Path
p=Path('outputs/octa-thick_v1/viewer.py')
s=p.read_text(encoding='utf-8')
for a,b in {
'Experimental thickness pilot':'Thickness pilot',
'Exploratory preview (estimated)':'Include unreliable measurements',
"'Preview · white stipple = estimated' if self.mode else 'Reported'":"'Including unreliable · white stipple' if self.mode else 'Unreliable excluded'",
"np.where(codes < 4,curve,np.nan)":"np.where(~v.unreliable[self.row,k],curve,np.nan)",
"np.where(codes >= 4,curve,np.nan)":"np.where(v.unreliable[self.row,k],curve,np.nan)",
"f'Experimental · finite {finite:.1f}% · reported {reported:.1f}% · estimated {est:.1f}% of native grid. '":"f'Coverage {finite:.1f}% · excluding unreliable {reported:.1f}% · unreliable included {est:.1f}% of native grid. '",
'No eligible endpoints. ILM is withheld for automatic full-retina/RNFL reporting; enable Exploratory preview to inspect saved U-Net ILM estimates. ':'No eligible measurements here. Try including unreliable measurements; shadows, exclusions and invalid positions remain blank. ',
'All automatic values are experimental.':'Available segmentation treated as usable for this pilot.',
"' · estimated' if record['estimated']":"' · unreliable' if record['estimated']",
'Dotted boundaries and white map stipple indicate estimates.':'Dotted boundaries and white map stipple indicate explicitly unreliable measurements.',
"'Preview (stipple = estimated)' if self.mode else 'Reported'":"'Including unreliable (stipple)' if self.mode else 'Unreliable excluded'",
' · Experimental':' · Pilot',
"f'{self.volume.scan_id}_points.csv'":"f'{self.volume.scan_id}_pilot_v2_points.csv'",
}.items():
 s=s.replace(a,b)
p.write_text(s,encoding='utf-8')
