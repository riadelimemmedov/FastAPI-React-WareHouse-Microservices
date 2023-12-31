#

#!FastApi
from fastapi import FastAPI,Header,HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.background import BackgroundTasks
from starlette.requests import Request


#!Models and Serializers
from models import redis,Order


#!Redis Orm
from redis_om.model import NotFoundError
from models import redis



#!Python modules and methods
from datetime import datetime
import httpx
import time
import json
from datetime import datetime,timedelta



#!Helpers methods
from utils.helpers import (check_user_token)


# Create FastApi object from FastAPI class
app = FastAPI(title="Payment")
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store the background tasks in a global dictionary using a unique identifier
background_tasks = {}


@app.get("/")
async def root():
    return {"message": "Payment and Order"}



#!get_all_orders
@app.get('/orders')
async def get_all_orders():
    """Get All Orders"""
    orders = Order.find((Order.slug=='order')).all()

    return orders



#!get_order
@app.get('/orders/{pk}')
async def get_order(pk:str):
    """Return specific order,for sended given value"""
    try:
        order = Order.get(pk=pk)
    except NotFoundError:
        return {'error': 'Order not found'},404
    return order



#!create_order
@app.post('/orders')
async def create_order(body:Order,background_tasks:BackgroundTasks,request:Request): 
    """Create a new order"""
    product_data = get_product_data(body.product_id)
    
    token = request.headers.get('Authorization').split()[1]
    user = await check_user_token(token)
    
        
    order = Order(
        product_id=body.product_id,
        customer_id=str(user['id']),
        product_name=product_data['name'],
        price=(product_data['price']*body.quantity),
        fee = 0.2 * (product_data['price'] * body.quantity),
        total = 1.2 * (product_data['price'] * body.quantity),
        quantity = body.quantity,
        status = 'pending'
    )
    if(order.pk):
        order.save()
        background_tasks.add_task(order_completed,order.pk)
    return order


#!cancel_order
@app.patch('/orders/cancel/{order_id}')
async def cancel_order(order_id:str,background_tasks:BackgroundTasks):
    """Cancel ordered goods"""
    try:
        pending_order = Order.get(pk=order_id)
        if pending_order.status=='pending':#
            # background_tasks.add_task(order_refunded,pending_order)
            pending_order.status = 'refunded'
            pending_order.save()    
        return pending_order
    except Exception as err:
        print('When want to refund order,system encounter some issues please try again')



#*update_product_data
def update_product_data(product_id,product_data):
    url = f"http://127.0.0.1:4000/products/{product_id}"
    
    try:
        with httpx.Client() as client:
            response = client.patch(url,json=product_data)
        response.raise_for_status()
        return True
    except httpx.HTTPError as http_err:
        return False
    

#*get_product_data
def get_product_data(product_id):
    url = f"http://127.0.0.1:4000/products/{product_id}"
    try:
        with httpx.Client() as client:
            response = client.get(url).json()
        return response
    except httpx.HTTPError as http_err:
        return {http_err}
    

#?order_completed
def order_completed(order_id:str):
    time.sleep(180)
    order = Order.get(pk=order_id)
    if order.status == 'refunded':
        print('Your order has been --- REFUNDED ---')        
    elif order.status == 'pending':
        # order.save()  
        print('Your order has been --- COMPLETED ---')
        order.status = 'completed'
        order.save()    
        updated_order = order.dict()
        deleted_fields = updated_order.pop('created_date')
        redis.xadd("order_completed",updated_order,'*')
    


#!delete_all_orders          
@app.delete('/orders')
async def delete_all_orders():
    """Delete all orders"""
    Order.find((Order.slug=='order')).delete()
    return {'success': 'Deleted all orders successfully'}



#!get_user_order
@app.get('/user/order')
async def get_user_order(request:Request):
    try:
        token = request.headers.get('Authorization').split()[1]
        user = await check_user_token(token)        
        orders = Order.find((Order.customer_id==str(user['id']))).all()
        return {'orders': orders,'user': user}
    except NotFoundError:
        return {'error': 'Order not found'},404
    
