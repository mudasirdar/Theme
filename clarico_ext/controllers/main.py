# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
from odoo import http, SUPERUSER_ID, api, tools
from odoo.http import request
import json
from odoo.addons.website_sale.controllers.main import WebsiteSale
import io
import csv
import base64
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError, ValidationError
from psycopg2 import IntegrityError

from odoo.addons.mail.models.mail_message import Message
from odoo.addons.website.controllers.main import Website
from odoo.addons.website_sale.controllers.main import TableCompute



	
def process(self, products, ppg=20, ppr=4):
	# Compute products positions on the grid
	minpos = 0
	index = 0
	maxy = 0
	x = 0
	for p in products:
		x = min(max(p.website_size_x, 1), ppr)
		y = min(max(p.website_size_y, 1), ppr)
		if index >= ppg:
			x = y = 1

		pos = minpos
		while not self._check_place(pos % ppr, pos // ppr, x, y, ppr):
			pos += 1
		# if 21st products (index 20) and the last line is full (ppr products in it), break
		# (pos + 1.0) / ppr is the line where the product would be inserted
		# maxy is the number of existing lines
		# + 1.0 is because pos begins at 0, thus pos 20 is actually the 21st block
		# and to force python to not round the division operation
		if index >= ppg and ((pos + 1.0) // ppr) > maxy:
			break

		if x == 1 and y == 1:   # simple heuristic for CPU optimization
			minpos = pos // ppr

		for y2 in range(1):
			for x2 in range(1):
				self.table[(pos // ppr) + y2][(pos % ppr) + x2] = False
		self.table[pos // ppr][pos % ppr] = {
#				 'product': p, 'x': x, 'y': y,
#				 'class': " ".join(x.html_class for x in p.website_style_ids if x.html_class)
			
			'product': p, 'x': 1, 'y': 1,
			'class': " ",
			
		}
		if index <= ppg:
			maxy = max(maxy, y + (pos // ppr))
		index += 1

	# Format table according to HTML needs
	rows = sorted(self.table.items())
	rows = [r[1] for r in rows]
	for col in range(len(rows)):
		cols = sorted(rows[col].items())
		x += len(cols)
		rows[col] = [r[1] for r in cols if r[1]]
	return rows
	   


TableCompute.process = process 


	
	
# @http.route('/', type='http', auth="public", website=True)
# def index(self, **kw):
# 	homepage = request.website.homepage_id
# 	if homepage and (homepage.sudo().is_visible or request.env.user.has_group('base.group_user')) and homepage.url != '/':
# 		return request.env['ir.http'].reroute(homepage.url)
# 
# 	return request.render('/', {})
# 	
# 	website_page = request.env['ir.http']._serve_page()
# 	if website_page:
# 		return website_page
# 	else:
# 		top_menu = request.website.menu_id
# 		first_menu = top_menu and top_menu.child_id and top_menu.child_id.filtered(lambda menu: menu.is_visible)
# 		if first_menu and first_menu[0].url not in ('/', '', '#') and (not (first_menu[0].url.startswith(('/?', '/#', ' ')))):
# 			return request.redirect(first_menu[0].url)
# 
# 	raise request.not_found()
# 
# 
# Website.index = index	


class WebsiteSale2(WebsiteSale):
	
	@http.route(['/shop/cart/update'], type='http', auth="public", methods=['GET', 'POST'], website=True,
			csrf=False)
	def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
		sale_order = request.website.sale_get_order(force_create=True)
		if sale_order.state != 'draft':
			request.session['sale_order_id'] = None
			sale_order = request.website.sale_get_order(force_create=True)

		product_custom_attribute_values = None
		if kw.get('product_custom_attribute_values'):
			product_custom_attribute_values = json.loads(kw.get('product_custom_attribute_values'))

		no_variant_attribute_values = None
		if kw.get('no_variant_attribute_values'):
			no_variant_attribute_values = json.loads(kw.get('no_variant_attribute_values'))


		if 'uom_id' in kw:
			sale_order._cart_update(
				product_id=int(product_id),
				add_qty=add_qty,
				set_qty=set_qty,
				product_uom_id= int(kw['uom_id']),
				product_custom_attribute_values=product_custom_attribute_values,
				no_variant_attribute_values=no_variant_attribute_values
			)
		else:
			sale_order._cart_update(
				product_id=int(product_id),
				add_qty=add_qty,
				set_qty=set_qty,
				product_custom_attribute_values=product_custom_attribute_values,
				no_variant_attribute_values=no_variant_attribute_values
			)

#		 if kw.get('express'):
#			 return request.redirect("/shop/checkout?express=1")

		return request.redirect("/shop/cart")


class EmiproThemeBase(http.Controller):
	
	@http.route(['/get_uom_price'], type='json', auth="public", website=True)
	def get_uom_price(self, **kw):
		
		uom = request.env['uom.uom'].sudo().browse(int(kw['uom']))
		ref = uom.uom_type
		
		price = float(kw['price'])
		if ref == 'bigger':
			factor = uom.factor_inv
			price = price * factor
		if ref == 'smaller':
			factor = uom.factor
			price = price / factor
		
		return json.dumps({'price': price})

	@http.route(['/quick_add_product_razzos'], type='http', auth="public", website=True, csrf=False)
	def quick_add_product_razzos(self, **kwargs):
		product = request.env['product.product'].sudo().search([('product_tmpl_id', '=', int(kwargs['id']))], limit=1)
		order = request.website.sale_get_order(force_create=1)
		if product:
			order._cart_update(product_id=product.id, product_uom= int(kwargs['unit']), line_id=None, add_qty=0, set_qty=int(kwargs['qty']))
		return json.dumps({'count': order.cart_quantity})
