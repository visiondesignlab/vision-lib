import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import cms_content
import store
import mediautil
import submissions
from submission_media import analyze_media, classify, public_link


class SubmissionsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, path in [('DATA',tmp.name),('CASES',tmp.name+'/cases.json'),('LOCK',tmp.name+'/.lock')]:
            patcher=patch.object(store,name,path);patcher.start();self.addCleanup(patcher.stop)
        self.body={'id':'1'*32,'url':'https://www.example.org/video?v=1','note':'private production note','title':'Film'}

    def test_private_and_retry(self):
        receipt=submissions.receive(self.body)
        self.assertEqual(receipt, {'receipt':self.body['id']})
        submissions.receive(dict(self.body,note='must not overwrite'))
        self.assertEqual(submissions.listing()['items'][0]['note'],self.body['note'])
        self.assertEqual(store.load_cases(),[])
        for url in ['file:///tmp/file', 'https://127.0.0.1/a', 'https://name:pass@example.org', 'http://localhost/']:
            with self.assertRaises(ValueError): public_link(url)

    def test_classification_needs_evidence(self):
        for text, expected in [('用了 AI 生成的首尾帧','video'),('Shot on iPhone','showcase'),
                               ('介绍 AI 生成工具',''),('真人实拍与 AI 合成',''),('OpenAI 发布新产品','')]:
            with self.subTest(text=text): self.assertEqual(classify('',text,'')[0],expected)

    def test_recovery_duplicate_and_private_receipt(self):
        submissions.receive(self.body)
        row=submissions.listing()['items'][0]
        report={'duration':3,'shots':[{'start':0,'end':3}],'steps':['生成首帧，再按镜头时间剪辑。']}
        completed=dict(media={'video':'/media/test.webm'},analysis=report,target='video')
        submissions.finish(row,completed)
        case=store.load_cases()[0]
        self.assertEqual(case['status'],'pending')
        self.assertEqual(case['shot_analysis'],report)
        self.assertNotIn(self.body['note'],json.dumps(cms_content.public_view(case)))
        submissions.receive(dict(self.body,id='2'*32))
        submissions.process(submissions.read()['items']['2'*32])
        self.assertEqual(len(store.load_cases()),1)
        self.assertEqual(submissions.read()['items']['2'*32]['status'],'duplicate')

    def test_manual_decision_survives_stale_background_job(self):
        submissions.receive(self.body);row=submissions.listing()['items'][0]
        submissions.review(row['id'],{'action':'archive','version':row['version']})
        submissions.finish(row,{'status':'needs_video'})
        self.assertEqual(submissions.listing()['items'][0]['status'],'archived')

    def test_local_shot_report_uses_video_measurements(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(store,'MEDIA',folder), patch.object(mediautil,'MEDIA',folder):
            video=Path(folder)/'example.mp4'
            subprocess.run([mediautil.FFMPEG,'-loglevel','error','-f','lavfi','-i','color=red:s=128x96:d=1:r=10',
                            '-f','lavfi','-i','color=blue:s=128x96:d=1:r=10','-filter_complex',
                            '[0:v][1:v]concat=n=2:v=1:a=0','-pix_fmt','yuv420p',str(video)],check=True)
            with patch('submission_media.frame_opinion',return_value={}):
                media,report,_=analyze_media(video,'sample')
            self.assertEqual(media['specs']['resolution'],'128×96')
            self.assertEqual([(s['start'],s['end']) for s in report['shots']],[(0,1),(1,2)])
            self.assertTrue((Path(folder)/report['shots'][0]['frame'].removeprefix('/media/')).is_file())
            self.assertTrue(report['steps'])

    def test_sync_retries_do_not_duplicate_or_drop_rows(self):
        response=[dict(self.body,seq=1,created='2026-11-05T00:00:00Z')]
        from io import BytesIO
        def open_page(req,timeout):
            self.assertEqual(req.get_header('Authorization'),'Bearer fixture')
            return BytesIO(json.dumps({'items':response if req.full_url.endswith('after=0') else []}).encode())
        with patch.object(submissions,'remote_config',return_value=('https://relay.example.org','fixture')), \
             patch('submissions.build_opener') as opener:
            opener.return_value.open.side_effect=open_page
            self.assertEqual(submissions.sync()['received'],1)
            self.assertEqual(submissions.sync()['received'],0)
        self.assertEqual(submissions.listing()['items'][0]['origin'],'pages')
