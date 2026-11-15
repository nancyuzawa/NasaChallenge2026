"""Dashboard/Activity integration with temporary synthetic Parquet parts."""
from datetime import date
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import duckdb
import pandas as pd
from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(FRONTEND))
import processed_data as store
import processed_activity as activity
from data import dashboard_series as reports_series
from activity_ui import calendar_html


class ProcessedPagesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"FIREWATCH_DATA": str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        sys.path.insert(0,str(FRONTEND.parent/'backend'))
        from src.fire_store import grid
        rows = []
        for sensor, count in (("MODIS",1),("VIIRS",2)):
            for month in (1,2,3):
                for i in range(count):
                    x,y = grid(-22.9,-47+i*.02)
                    rows.append(dict(sensor=sensor,satellite=sensor,acq_date=f"2024-{month:02d}-10",acq_time="0005",
                                     latitude=-22.9,longitude=-47+i*.02,cell_x=x,cell_y=y,confidence="low",frp=1.,source_file="fixture"))
        for i in range(4):
            x,y=grid(-22.9,-47+i*.02)
            rows.append(dict(sensor="VIIRS",satellite="VIIRS",acq_date="2025-01-10",acq_time="0005",latitude=-22.9,
                             longitude=-47+i*.02,cell_x=x,cell_y=y,confidence="low",frp=1.,source_file="fixture"))
        self.frame=pd.DataFrame(rows)
        self.write()
        self.filters=dict(country="Brazil",state="All regions",city=None,latitude=-22.9,longitude=-47,
                          period=(date(2025,1,1),date(2025,12,31)))

    def write(self):
        conn=duckdb.connect(':memory:')
        try:
            for (sensor,year),frame in self.frame.groupby([self.frame.sensor,self.frame.acq_date.str[:4]]):
                target=self.root/sensor.lower()/year/'brazil'/'part-001.parquet'
                target.parent.mkdir(parents=True,exist_ok=True)
                conn.register('fixture',frame)
                conn.table('fixture').write_parquet(str(target))
                conn.unregister('fixture')
        finally:
            conn.close()

    def test_harmonized_activity_matches_dashboard_and_keeps_missing_days_unknown(self):
        values=store.dashboard_series(self.filters['period'],self.filters)
        self.assertEqual(values[0],2.)
        self.assertIsNone(values[1])
        self.assertEqual(activity.annual_series(2025,self.filters),values)
        cells=activity.calendar_cells(2025,1,self.filters)
        self.assertEqual(sum(c['count'] or 0 for c in cells),2.)
        self.assertIsNone(cells[0]['count'])
        self.assertIn('No observations',calendar_html(cells,activity.heat_legend(c['count'] for c in cells)))
        self.assertEqual(activity.month_summary(2025,1,self.filters)['total'],2.)
        self.assertEqual(activity.annual_series(2025,self.filters,['VIIRS'])[0],4.)
        self.assertIsNone(activity.annual_series(2025,self.filters,['MODIS'])[0])

    def test_cache_invalidates_without_changing_reports_adapter(self):
        expected=reports_series(self.filters['period'],self.filters)
        self.assertEqual(store.dashboard_metrics(self.filters['period'],self.filters)['hotspots'],4)
        self.frame=self.frame[~((self.frame.acq_date=='2025-01-10') & (self.frame.longitude > -46.99))]
        self.write()
        self.assertEqual(store.dashboard_metrics(self.filters['period'],self.filters)['hotspots'],1)
        self.assertEqual(reports_series(self.filters['period'],self.filters),expected)

    def test_dashboard_and_activity_render_real_parquets_and_month_details(self):
        app=AppTest.from_file(str(FRONTEND/'app.py'),default_timeout=30).run()
        app.session_state.filters=self.filters
        app.switch_page('pages/1_Dashboard.py').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Parquet / DuckDB' in m.value for m in app.markdown))
        app.switch_page('pages/2_Activity.py').run()
        self.assertFalse(app.exception)
        self.assertIn('2024',[str(v) for v in app.selectbox(key='calendar_year').options])
        app.selectbox(key='calendar_year').select(2025).run()
        app.selectbox(key='calendar_month').select(1).run()
        app.button(key='see-month-details').click().run()
        self.assertFalse(app.exception)
        app.get('button_group')[0].set_value(['MODIS']).run()
        self.assertFalse(app.exception)


class SpatialBatchTest(unittest.TestCase):
    def test_batch_matches_scalar_for_holes_edges_and_multiple_polygons(self):
        import numpy as np
        outer=[[0,0],[4,0],[4,4],[0,4],[0,0]]
        hole=[[1,1],[2,1],[2,2],[1,2],[1,1]]
        island=[[7,7],[8,7],[8,8],[7,8],[7,7]]
        geometry=dict(type="MultiPolygon",coordinates=[[outer,hole],[island]])
        rng=np.random.default_rng(42)
        points=np.vstack([rng.uniform(-1,9,(5000,2)),np.array(outer+hole+island)])
        expected=[store._contains(geometry,y,x) for x,y in points]
        np.testing.assert_array_equal(store._contains_many(geometry,points[:,1],points[:,0]),expected)

    def test_radius_sql_handles_antimeridian(self):
        with duckdb.connect(':memory:') as conn:
            clause,params=store._spatial(conn,dict(scope="radius",latitude=0,longitude=179.9,radius_km=30))
            result=conn.execute(f"SELECT longitude FROM (VALUES (0.,-179.9),(0.,170.)) t(latitude,longitude) WHERE {clause}",params).fetchall()
        self.assertEqual(len(result),1)
        self.assertAlmostEqual(float(result[0][0]),-179.9)


class DashboardSummaryTest(unittest.TestCase):
    setUp = ProcessedPagesTest.setUp
    write = ProcessedPagesTest.write

    def test_pruning_preserves_results_and_reuses_summary_after_memory_reset(self):
        import dashboard_data as dashboard
        other = self.root/'modis/2025/albania/part-001.parquet'
        other.parent.mkdir(parents=True)
        far = self.frame.iloc[:1].copy()
        far['latitude'],far['longitude'],far['acq_date'] = 70.,100.,'2025-01-10'
        far.to_parquet(other,index=False)
        future = self.root/'modis/2030/brazil/part-001.parquet'
        future.parent.mkdir(parents=True)
        self.frame.iloc[:1].to_parquet(future,index=False)
        selected=dashboard._candidates(self.root,self.filters,2025)
        self.assertNotIn(str(other.resolve()),[item[0] for item in selected])
        self.assertNotIn(str(future.resolve()),[item[0] for item in selected])
        expected=store.dashboard_metrics(self.filters['period'],self.filters)
        metrics,values,_=dashboard.load_dashboard(self.filters['period'],self.filters)
        self.assertEqual(metrics['hotspots'],expected['hotspots'])
        self.assertEqual(metrics['current_period'],4)
        self.assertEqual(metrics['peak_count'],4)
        self.assertEqual(metrics['peak_month'],'January')
        self.assertEqual(values[0],4)
        self.assertEqual(sum(v or 0 for v in values),metrics['hotspots'])
        dashboard._summary.cache_clear()
        with patch('dashboard_data.daily_aggregation',side_effect=AssertionError('must use disk summary')):
            cached=dashboard.load_dashboard(self.filters['period'],self.filters)
        self.assertEqual(cached[0],metrics)
        self.assertTrue(list((self.root/'.dashboard_cache').glob('*.parquet')))

    def test_changed_parts_invalidate_summary_and_missing_statistics_keep_file(self):
        import dashboard_data as dashboard
        from src.fire_store import grid
        first=dashboard.load_dashboard(self.filters['period'],self.filters)[0]
        self.frame=self.frame[~((self.frame.acq_date=='2025-01-10') & (self.frame.longitude > -46.99))]
        self.write()
        self.assertEqual(first['hotspots'],4)
        self.assertEqual(dashboard.load_dashboard(self.filters['period'],self.filters)[0]['hotspots'],1)
        import pyarrow as pa
        import pyarrow.parquet as pq
        path=self.root/'viirs/2025/unknown/part-001.parquet'
        path.parent.mkdir(parents=True)
        pq.write_table(pa.Table.from_pandas(self.frame.iloc[-1:],preserve_index=False),path,write_statistics=False)
        selected=dashboard._candidates(self.root,self.filters,2025)
        self.assertIn(str(path.resolve()),[item[0] for item in selected])


class DashboardLatestYearTest(unittest.TestCase):
    setUp = ProcessedPagesTest.setUp
    write = ProcessedPagesTest.write

    def test_latest_year_overrides_welcome_default_but_preserves_later_selection(self):
        newer=self.frame.iloc[-1:].copy()
        newer['acq_date']='2026-01-10'
        self.frame=pd.concat([self.frame,newer],ignore_index=True)
        self.write()
        app=AppTest.from_file(str(FRONTEND/'app.py'),default_timeout=30).run()
        app.session_state.filters=self.filters.copy()
        app.switch_page('pages/1_Dashboard.py').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.filters['period'],(date(2026,1,1),date(2026,12,31)))
        chosen=(date(2024,2,1),date(2024,3,31))
        app.session_state.filters={**app.session_state.filters,'period':chosen}
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.filters['period'],chosen)


class DashboardDateFilterTest(unittest.TestCase):
    setUp = ProcessedPagesTest.setUp
    write = ProcessedPagesTest.write

    def test_old_year_partial_range_apply_reopen_and_reset(self):
        older=self.frame.iloc[:1].copy()
        older['acq_date']='2000-01-10'
        self.frame=pd.concat([self.frame,older],ignore_index=True)
        self.write()
        app=AppTest.from_file(str(FRONTEND/'app.py'),default_timeout=30).run()
        app.session_state.filters=self.filters.copy()
        app.switch_page('pages/1_Dashboard.py').run()
        app.button(key='filter').click().run()
        field=app.date_input(key='dashboard_filter_period')
        self.assertIn('2000',field.proto.min)
        chosen=(date(2000,1,10),date(2000,1,10))
        field.set_value(chosen)
        next(b for b in app.button if b.label=='Apply').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.filters['period'],chosen)
        self.assertTrue(any('10/01/2000 to 10/01/2000' in m.value for m in app.markdown))
        app.button(key='filter').click().run()
        self.assertEqual(tuple(app.date_input(key='dashboard_filter_period').value),chosen)
        next(b for b in app.button if b.label=='Reset').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.filters['period'],(date(2025,1,1),date(2025,12,31)))

    def test_incomplete_range_is_not_applied(self):
        app=AppTest.from_file(str(FRONTEND/'app.py'),default_timeout=30).run()
        app.session_state.filters=self.filters.copy()
        app.switch_page('pages/1_Dashboard.py').run()
        before=app.session_state.filters['period']
        app.button(key='filter').click().run()
        app.date_input(key='dashboard_filter_period').set_value((date(2024,2,1),))
        next(b for b in app.button if b.label=='Apply').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertEqual(app.session_state.filters['period'],before)


class DashboardHotspotsTest(unittest.TestCase):
    setUp=ProcessedPagesTest.setUp
    write=ProcessedPagesTest.write

    def test_right_cards_and_trend_use_observations_not_harmonized_cells(self):
        import dashboard_data as dashboard
        metrics,values,_=dashboard.load_dashboard(self.filters['period'],self.filters)
        self.assertEqual(values[0],4)
        self.assertEqual(store.dashboard_series(self.filters['period'],self.filters)[0],2)
        self.assertIsNone(metrics['historical_growth'])  # different sensors in earlier year
        app=AppTest.from_file(str(FRONTEND/'app.py'),default_timeout=30).run()
        app.session_state.filters=self.filters.copy()
        app.switch_page('pages/1_Dashboard.py').run()
        self.assertFalse(app.exception)
        content=' '.join(m.value for m in app.markdown)
        self.assertIn('January',content)
        self.assertIn('4 Hotspots',content)
        self.assertIn('Monthly trend in fire outbreaks',content)
        self.assertNotIn('Cell-days',content)
        self.assertNotIn('cell-days',content)


class GlobeHotspotsTest(unittest.TestCase):
    setUp=ProcessedPagesTest.setUp
    write=ProcessedPagesTest.write

    def test_both_sensors_period_country_and_display_limit(self):
        import dashboard_data as dashboard
        selection=(date(2024,1,1),date(2024,1,31))
        payload=dashboard.load_hotspots(selection,self.filters)
        self.assertEqual({p['sensor'] for p in payload['points']},{'MODIS','VIIRS'})
        self.assertEqual(payload['shown'],3)
        self.assertFalse(payload['limited'])
        reduced=dashboard.load_hotspots(selection,self.filters,limit_per_sensor=1)
        self.assertEqual(reduced['shown'],2)
        self.assertEqual(reduced['total'],3)
        self.assertTrue(reduced['limited'])
        empty=dashboard.load_hotspots((date(2030,1,1),date(2030,1,31)),self.filters)
        self.assertEqual(empty['points'],[])
        other=dashboard.load_hotspots(selection,{**self.filters,'country':'Argentina'})
        self.assertEqual(other['points'],[])

    def test_globe_receives_red_marker_payload_without_changing_city_selection(self):
        import globe
        import dashboard_data as dashboard
        payload=dashboard.load_hotspots(self.filters['period'],self.filters)
        with patch.object(globe,'_component',return_value=None) as component:
            globe.render_globe(self.filters,hotspots=payload)
        self.assertEqual(component.call_args.kwargs['hotspots'],payload)
        self.assertEqual(component.call_args.kwargs['selection']['country_iso'],'BRA')
        self.assertEqual(payload['shown'],4)


class StateBoundaryDashboardTest(unittest.TestCase):
    write=ProcessedPagesTest.write

    def setUp(self):
        ProcessedPagesTest.setUp(self)
        from src.fire_store import grid
        extra=[]
        for sensor,lat,lon in [('MODIS',-15.8,-47.9),('VIIRS',-15.8,-47.9),('VIIRS',-16.2,-48.1)]:
            row=self.frame.iloc[-1].to_dict()
            x,y=grid(lat,lon)
            row.update(sensor=sensor,satellite=sensor,latitude=lat,longitude=lon,cell_x=x,cell_y=y)
            extra.append(row)
        self.frame=pd.concat([self.frame,pd.DataFrame(extra)],ignore_index=True)
        self.write()

    def test_district_polygon_excludes_nearby_goias_before_limiting_and_cache_changes(self):
        import dashboard_data as dashboard
        selected={**self.filters,'state':'Distrito Federal','latitude':-15.7814,'longitude':-47.918}
        payload=dashboard.load_hotspots(selected['period'],selected)
        self.assertEqual(payload['shown'],2)
        self.assertEqual({p['sensor'] for p in payload['points']},{'MODIS','VIIRS'})
        self.assertTrue(all(p['latitude']==-15.8 for p in payload['points']))
        self.assertEqual(dashboard.load_dashboard(selected['period'],selected)[0]['hotspots'],2)
        country=dashboard.load_hotspots(selected['period'],self.filters)
        self.assertEqual(country['shown'],7)
        state=dashboard.load_hotspots(selected['period'],{**selected,'state':'São Paulo'})
        self.assertEqual(state['shown'],4)

    def test_selected_state_is_shown_in_badge_and_unavailable_regions_do_not_fall_back(self):
        import dashboard_data as dashboard
        selected={**self.filters,'state':'Distrito Federal','latitude':-15.7814,'longitude':-47.918}
        app=AppTest.from_file(str(FRONTEND/'app.py'),default_timeout=30).run()
        app.session_state.filters=selected
        app.switch_page('pages/1_Dashboard.py').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Brazil · Distrito Federal' in m.value for m in app.markdown))
        invalid=dashboard.load_hotspots(selected['period'],{**selected,'state':'Unknown province'})
        self.assertFalse(invalid['boundary_available'])
        self.assertEqual(invalid['points'],[])


class GlobeStateOutlineTest(unittest.TestCase):
    def test_selected_polygon_is_passed_and_cleared_for_country_selection(self):
        import globe
        filters=dict(country='Brazil',state='Distrito Federal',city=None,latitude=-15.8,longitude=-47.9)
        with patch.object(globe,'_component',return_value=None) as component:
            globe.render_globe(filters)
            boundary=component.call_args.kwargs['selection']['boundary']
            self.assertEqual(boundary['properties']['name'],'Distrito Federal')
            self.assertIn(boundary['geometry']['type'],('Polygon','MultiPolygon'))
            globe.render_globe({**filters,'state':'All regions'})
            self.assertIsNone(component.call_args.kwargs['selection']['boundary'])


class RegionsByYearTest(unittest.TestCase):
    setUp=StateBoundaryDashboardTest.setUp
    write=ProcessedPagesTest.write

    def test_new_regions_are_offered_only_when_period_has_observations(self):
        import dashboard_data as dashboard
        from locations import REGIONS
        self.assertNotIn('Goiás',REGIONS['Brazil'])
        current=dashboard.available_regions('Brazil',(date(2025,1,1),date(2025,12,31)))
        self.assertIn('Goiás',current)
        self.assertIn('Distrito Federal',current)
        self.assertIn('São Paulo',current)
        earlier=dashboard.available_regions('Brazil',(date(2024,1,1),date(2024,12,31)))
        self.assertIn('São Paulo',earlier)
        self.assertNotIn('Goiás',earlier)
        self.assertNotIn('Distrito Federal',earlier)
        self.assertEqual(dashboard.available_regions('Brazil',(date(2030,1,1),date(2030,12,31))),{})

    def test_dialog_date_change_updates_state_options_and_new_state_applies(self):
        app=AppTest.from_file(str(FRONTEND/'app.py'),default_timeout=30).run()
        app.session_state.filters=self.filters.copy()
        app.switch_page('pages/1_Dashboard.py').run()
        app.button(key='filter').click().run()
        states=next(s for s in app.selectbox if s.label=='State/Province')
        self.assertIn('Goiás',states.options)
        app.date_input(key='dashboard_filter_period').set_value((date(2024,1,1),date(2024,12,31))).run()
        states=next(s for s in app.selectbox if s.label=='State/Province')
        self.assertNotIn('Goiás',states.options)
        app.date_input(key='dashboard_filter_period').set_value((date(2025,1,1),date(2025,12,31))).run()
        next(s for s in app.selectbox if s.label=='State/Province').select('Goiás').run()
        next(b for b in app.button if b.label=='Apply').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.filters['state'],'Goiás')
        self.assertTrue(any('Brazil · Goiás' in m.value for m in app.markdown))
