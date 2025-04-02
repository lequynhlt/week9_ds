from django.shortcuts import render
import csv
import json
from datetime import datetime
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import Customer, ProductGroup, Product, Order, OrderDetail
from django.db.models import Sum, F, Count, Func
from django.db.models.functions import ExtractMonth, ExtractQuarter, ExtractWeekDay, ExtractDay
from django.db import DatabaseError

@require_POST
@csrf_exempt
def import_csv(request):
    try:
        csv_file_path = 'data/data_ggsheet.csv'
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                name = row['Tên khách hàng'] if row['Tên khách hàng'] else None
                customer, _ = Customer.objects.get_or_create(
                    customer_id=row['Mã khách hàng'],
                    defaults={
                        'name': name,
                        'segment_code': row['Mã PKKH']
                    }
                )
                group, _ = ProductGroup.objects.get_or_create(
                    group_code=row['Mã nhóm hàng'],
                    defaults={'group_name': row['Tên nhóm hàng']}
                )
                try:
                    unit_price = int(row['Đơn giá'])
                except (ValueError, KeyError):
                    unit_price = 0
                product, _ = Product.objects.get_or_create( 
                    product_code=row['Mã mặt hàng'],
                    defaults={
                        'name': row['Tên mặt hàng'],
                        'group': group,
                        'unit_price': unit_price
                    }
                )
                order_time = datetime.strptime(row['Thời gian tạo đơn'], '%Y-%m-%d %H:%M:%S')
                order, _ = Order.objects.get_or_create(
                    order_id=row['Mã đơn hàng'],
                    defaults={
                        'customer': customer,
                        'order_time': order_time
                    }
                )
                order_detail, created = OrderDetail.objects.get_or_create(
                    order=order,
                    product=product,
                    defaults={'quantity': int(row['SL'])}
                )
                if not created:
                    order_detail.quantity += int(row['SL'])
                    order_detail.save()

        return HttpResponse("Data imported successfully!")
    except FileNotFoundError:
        return HttpResponse("Error: CSV file not found.", status=400)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)
    
def data_visualization(request):
    try:
        # Q1
        aggregated_data = OrderDetail.objects.values(
            'product__group__group_code',
            'product__group__group_name'
        ).annotate(
            SL=Sum('quantity'),
            Thành_tiền=Sum(F('quantity') * F('product__unit_price'))
        )
        data_for_q1 = [
            {
                'Mã nhóm hàng': item['product__group__group_code'],
                'Tên nhóm hàng': item['product__group__group_name'],
                'Thành tiền': item['Thành_tiền'],
                'SL': item['SL']
            }
            for item in aggregated_data
        ]
        # Q2
        order_details = OrderDetail.objects.select_related('order', 'product__group').values(
            'product__group__group_code',
            'product__group__group_name',
            'product__product_code',
            'product__name',
            'quantity',
            'product__unit_price'
        )
        data_for_q2 = [
            {
                'Mã nhóm hàng': detail['product__group__group_code'],
                'Tên nhóm hàng': detail['product__group__group_name'],
                'Mã mặt hàng': detail['product__product_code'],
                'Tên mặt hàng': detail['product__name'],
                'Thành tiền': detail['quantity'] * detail['product__unit_price'],
                'SL': detail['quantity']
            }
            for detail in order_details
        ]
        # Q3
        order_count_data = OrderDetail.objects.values(
            'product__group__group_code',
            'product__group__group_name',
            'product__unit_price',
            'order__order_id'
        ).annotate(
            order_count=Count('order__order_id', distinct=True)
        )
        data_for_q3 = [
            {
                'Nhóm hàng': f"[{item['product__group__group_code']}] {item['product__group__group_name']}",
                'Đơn giá': item['product__unit_price'],
                'Số lượng đơn hàng': item['order_count']
            }
            for item in order_count_data
        ]
        # Q4
        quarter_data = OrderDetail.objects.values(
            quarter=ExtractQuarter('order__order_time')  
        ).annotate(
            SL=Sum('quantity'),
            Thành_tiền=Sum(F('quantity') * F('product__unit_price'))
        )
        data_for_q4 = [
            {
                'Quý': f"Q{item['quarter']}", 
                'Thành tiền': item['Thành_tiền'],
                'SL': item['SL']
            }
            for item in quarter_data
        ]
        # Q5
        month_data = OrderDetail.objects.values(
            month=ExtractMonth('order__order_time')
        ).annotate(
            SL=Sum('quantity'),
            Thành_tiền=Sum(F('quantity') * F('product__unit_price'))
        )
        data_for_q5 = [
            {
                'Tháng': f"{item['month']:02d}",
                'Thành tiền': item['Thành_tiền'],
                'SL': item['SL']
            }
            for item in month_data
        ]
        # Q6
        day_data = OrderDetail.objects.values(
            day=ExtractDay('order__order_time'),
            date=Func('order__order_time', function='DATE')
        ).annotate(
            SL=Sum('quantity'),
            Thành_tiền=Sum(F('quantity') * F('product__unit_price'))
        )
        day_dict = {}
        for item in day_data:
            day = item['day']
            day_name = f"Ngày {day:02d}"
            if day_name not in day_dict:
                day_dict[day_name] = {'Thành tiền': 0, 'SL': 0, 'Ngày tạo đơn': set()}
            day_dict[day_name]['Thành tiền'] += item['Thành_tiền']
            day_dict[day_name]['SL'] += item['SL']
            day_dict[day_name]['Ngày tạo đơn'].add(str(item['date']))
        data_for_q6 = [
            {
                'Ngày trong tháng': day_name,
                'Thành tiền': values['Thành tiền'],
                'SL': values['SL'],
                'Doanh số bán TB': values['Thành tiền'] / len(values['Ngày tạo đơn']),
                'Số lượng bán TB': values['SL'] / len(values['Ngày tạo đơn'])
            }
            for day_name, values in day_dict.items()
        ]
        data_for_q6.sort(key=lambda x: int(x['Ngày trong tháng'].split(' ')[1]))

        # Q7
        weekday_data = OrderDetail.objects.values(
            weekday=ExtractWeekDay('order__order_time'),
            date=Func('order__order_time', function='DATE')
        ).annotate(
            SL=Sum('quantity'),
            Thành_tiền=Sum(F('quantity') * F('product__unit_price'))
        )
        weekday_dict = {}
        for item in weekday_data:
            weekday = item['weekday']
            weekday_name = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"][weekday - 1]
            if weekday_name not in weekday_dict:
                weekday_dict[weekday_name] = {'Thành tiền': 0, 'SL': 0, 'Ngày tạo đơn': set()}
            weekday_dict[weekday_name]['Thành tiền'] += item['Thành_tiền'] or 0
            weekday_dict[weekday_name]['SL'] += item['SL'] or 0
            weekday_dict[weekday_name]['Ngày tạo đơn'].add(str(item['date']))
        data_for_q7 = [
            {
                'Thứ': weekday_name,
                'Thành tiền': values['Thành tiền'],
                'SL': values['SL'],
                'Doanh số bán TB': values['Thành tiền'] / len(values['Ngày tạo đơn']) if values['Ngày tạo đơn'] else 0,
                'Số lượng bán TB': values['SL'] / len(values['Ngày tạo đơn']) if values['Ngày tạo đơn'] else 0
            }
            for weekday_name, values in weekday_dict.items()
        ]
        weekdays_order = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        data_for_q7.sort(key=lambda x: weekdays_order.index(x['Thứ']))

        # Q8
        order_month_group_data = OrderDetail.objects.values(
            'order__order_id',
            'order__order_time',
            'product__group__group_code',
            'product__group__group_name'
        ).annotate(
            SL=Sum('quantity'),
            Thành_tiền=Sum(F('quantity') * F('product__unit_price'))
        )
        total_orders_by_month = Order.objects.values(
            month=ExtractMonth('order_time')
        ).annotate(
            total_orders=Sum(1)
        )
        total_orders_dict = {f"Tháng {item['month']:02d}": item['total_orders'] for item in total_orders_by_month}
        month_group_dict = {}
        for item in order_month_group_data:
            month = f"Tháng {item['order__order_time'].strftime('%m')}"
            group_name = f"[{item['product__group__group_code']}] {item['product__group__group_name']}"
            key = f"{month}|{group_name}"
            if key not in month_group_dict:
                month_group_dict[key] = {
                    'Tháng': month,
                    'Nhóm hàng': group_name,
                    'Mã đơn hàng': set(),
                    'SL': 0,
                    'Thành tiền': 0
                }
            month_group_dict[key]['Mã đơn hàng'].add(item['order__order_id'])
            month_group_dict[key]['SL'] += item['SL']
            month_group_dict[key]['Thành tiền'] += item['Thành_tiền']
        data_for_q8 = [
            {
                'Tháng': values['Tháng'],
                'Nhóm hàng': values['Nhóm hàng'],
                'SL': values['SL'],
                'Thành tiền': values['Thành tiền'],
                'SL Đơn Bán': len(values['Mã đơn hàng']),
                'Xác suất bán': (len(values['Mã đơn hàng']) / total_orders_dict.get(values['Tháng'], 1)) * 100
            }
            for key, values in month_group_dict.items()
        ]
        data_for_q8.sort(key=lambda x: (x['Tháng'], x['Nhóm hàng']))

        # Q9
        age_group_data = OrderDetail.objects.values(
            'order__customer__segment_code'
        ).annotate(
            total_revenue=Sum(F('quantity') * F('product__unit_price'))
        )
        def extract_age_group(segment_code):
            segment_choices = dict(Customer.SEGMENT_CHOICES)
            description = segment_choices.get(segment_code, "Không xác định")
            try:
                start = description.index('(') + 1
                end = description.index(')')
                raw_age = description[start:end].replace(' tuổi', '').strip()
                return '45+' if raw_age == '45+' else raw_age
            except ValueError:
                return 'Không xác định'
        data_for_q9 = [
            {
                'Mã PKKH': item['order__customer__segment_code'],
                'Nhóm tuổi': extract_age_group(item['order__customer__segment_code']),
                'Doanh số bán': item['total_revenue']
            }
            for item in age_group_data
        ]
        data_for_q9.sort(key=lambda x: x['Mã PKKH'])

        # Q10
        purchase_count_data = Order.objects.values('customer__customer_id').annotate(
            purchase_count=Count('order_id', distinct=True)
        ).values('purchase_count').annotate(
            customer_count=Count('customer__customer_id', distinct=True)
        )
        data_for_q10 = [
            {
                'Số lượt mua hàng': item['purchase_count'],
                'SL khách hàng': item['customer_count']
            }
            for item in purchase_count_data
        ]
        data_for_q10.sort(key=lambda x: x['Số lượt mua hàng'])

        return render(request, 'visualization.html', {
            'data_for_q1': json.dumps(data_for_q1, default=str),
            'data_for_q2': json.dumps(data_for_q2, default=str),
            'data_for_q3': json.dumps(data_for_q3, default=str),
            'data_for_q4': json.dumps(data_for_q4, default=str),
            'data_for_q5': json.dumps(data_for_q5, default=str),
            'data_for_q6': json.dumps(data_for_q6, default=str),
            'data_for_q7': json.dumps(data_for_q7, default=str),
            'data_for_q8': json.dumps(data_for_q8, default=str),
            'data_for_q9': json.dumps(data_for_q9, default=str),
            'data_for_q10': json.dumps(data_for_q10, default=str),
        })

    except DatabaseError as e:
        return HttpResponse(f"Database Error: {str(e)}", status=500)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)