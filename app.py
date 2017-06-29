import json

from sqlalchemy import create_engine, func, Column, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from tornado import websocket, web, ioloop

engine = create_engine('sqlite:///:memory:', echo=True)
Base = declarative_base()


class Order(Base):
    __tablename__ = 'order'

    id = Column(Integer, primary_key=True)
    amount = Column(Integer)

    def __repr__(self):
        return "<Order(id={}, amount={})>".format(self.id, self.amount)


Base.metadata.create_all(engine)
Session = sessionmaker()
Session.configure(bind=engine)
session = Session()

# 报表系统所有链接ws的客户端
rpt_ws_cl = []


class IndexHandler(web.RequestHandler):
    """报表系统首页"""

    def get(self):
        self.render("index.html")

    def data_received(self, chunk):
        pass


class SocketHandler(websocket.WebSocketHandler):
    """报表系统websocket连接"""

    def check_origin(self, origin):
        return True

    def open(self):
        # 查询今日订单
        if self not in rpt_ws_cl:
            rpt_ws_cl.append(self)
            self.write_message(json.dumps({"cnt": session.query(Order).count(),
                                           "amount": session.query(func.sum(Order.amount)).scalar()}))

    def on_close(self):
        if self in rpt_ws_cl:
            rpt_ws_cl.remove(self)

    def on_message(self, message):
        pass

    def data_received(self, chunk):
        pass


class ApiHandler(web.RequestHandler):
    """订单中心支付宝支付成功回调接口"""

    @web.asynchronous
    def get(self, *args):
        # 回调逻辑，数据库写入
        order_id = int(self.get_argument("id"))
        order_amount = int(self.get_argument("amount"))

        new_order_flag = False
        if session.query(Order.id).filter_by(id=order_id).scalar():
            # 支付成功重复回调的情况，严谨起见还应该处理回调信息不一致的情况
            print("重复回调")
            pass
        else:
            # 增加订单记录；现实世界中，这里通常是改变订单的状态
            session.add(Order(id=order_id, amount=order_amount))
            session.commit()
            new_order_flag = True
        self.finish()
        # 请求完成后，异步通过ws发送消息到客户端
        if new_order_flag:
            data = {"cnt": session.query(Order).count(), "amount": session.query(func.sum(Order.amount)).scalar()}
            data = json.dumps(data)
            for c in rpt_ws_cl:
                c.write_message(data)

    @web.asynchronous
    def post(self):
        pass

    def data_received(self, chunk):
        pass


app = web.Application([
    (r'/', IndexHandler),
    (r'/ws', SocketHandler),
    (r'/order_center/order/alipay/callback', ApiHandler),
    (r'/(favicon.ico)', web.StaticFileHandler, {'path': '../'}),
    (r'/(architecture.png)', web.StaticFileHandler, {'path': './'}),
])

if __name__ == '__main__':
    app.listen(8888)
    ioloop.IOLoop.instance().start()
