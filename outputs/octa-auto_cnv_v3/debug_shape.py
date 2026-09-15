from common import *
from test_workflow import ShapeTests
from algorithm import detect
obj=ShapeTests();a=obj.rounded();a['automatic_thickness_um'][:]=np.nan;c,r=detect(a)
print([(z['pixels'],z['diameter_um'],z['circularity'],z['screen_reasons']) for z in json.loads(str(c['screened_records_json']))]);print('accepted',len(r))
