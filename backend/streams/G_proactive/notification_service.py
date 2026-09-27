"""In-app delivery only. No private mood or provider identifiers in a couple notification."""
import logging
from uuid import uuid4
from backend.db import now

class NotificationService:
    def __init__(self,db):self.db=db

    def send_date_proposal_notification(self,couple_id,date_plan,suggestion_id,score):
        with self.db.connect() as c:
            inserted=c.execute('INSERT OR IGNORE INTO v2_notifications VALUES(?,?,?,?,?,?)',
                (uuid4().hex,couple_id,suggestion_id,date_plan['id'],score,now())).rowcount
        if inserted:logging.getLogger(__name__).info('date_proposal_notification delivered in_app score=%.3f',score)

    def list(self,member):
        with self.db.connect() as c:
            rows=c.execute("SELECT n.*,r.user_id AS seen FROM v2_notifications n JOIN v2_suggestions s ON s.id=n.suggestion_id LEFT JOIN v2_notification_reads r ON r.notification_id=n.id AND r.user_id=? WHERE n.couple_id=? AND s.state IN ('new','viewed','accepted') ORDER BY n.created_at DESC LIMIT 20",(member['id'],member['couple_id'])).fetchall()
        return {'items':[{'id':r['id'],'plan_id':r['plan_id'],'created_at':r['created_at'],
                          'read':bool(r['seen']),'title':'Une idée de sortie à deux ?',
                          'message':'Un programme vous attend. Consultez les horaires et confirmez ensemble.'} for r in rows]}

    def read(self,member,nid):
        with self.db.connect() as c:
            if not c.execute('SELECT 1 FROM v2_notifications WHERE id=? AND couple_id=?',(nid,member['couple_id'])).fetchone():raise KeyError('Notification inconnue')
            c.execute('INSERT OR IGNORE INTO v2_notification_reads VALUES(?,?)',(nid,member['id']))
        return {'read':True}
