# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from odoo import SUPERUSER_ID
import io
import csv
import base64
import ftplib
from odoo.tools import pycompat
from odoo.exceptions import UserError, AccessError

from odoo.addons.website_mail.models.mail_message import MailMessage
from datetime import datetime, timedelta

from odoo.addons.website_sale.models.sale_order import SaleOrder


def _cart_update(self, product_id=None, line_id=None, add_qty=0, set_qty=0, **kwargs):
		""" Method monkey patched to handle multiple UoM from website """
		self.ensure_one()
		print (kwargs, 'In Override method \n\n\n\n\n\n\n')
		product_context = dict(self.env.context)
		product_context.setdefault('lang', self.sudo().partner_id.lang)
		SaleOrderLineSudo = self.env['sale.order.line'].sudo().with_context(product_context)
		# change lang to get correct name of attributes/values
		product_with_context = self.env['product.product'].with_context(product_context)
		product = product_with_context.browse(int(product_id))

		try:
			if add_qty:
				add_qty = float(add_qty)
		except ValueError:
			add_qty = 1
		try:
			if set_qty:
				set_qty = float(set_qty)
		except ValueError:
			set_qty = 0
		quantity = 0
		order_line = False
		if self.state != 'draft':
			request.session['sale_order_id'] = None
			raise UserError(_('It is forbidden to modify a sales order which is not in draft status.'))
		if line_id is not False:
			order_line = self._cart_find_product_line(product_id, line_id, **kwargs)[:1]

		# Create line if no line with product_id can be located
		if not order_line:
			if not product:
				raise UserError(_("The given product does not exist therefore it cannot be added to cart."))

			no_variant_attribute_values = kwargs.get('no_variant_attribute_values') or []
			received_no_variant_values = product.env['product.template.attribute.value'].browse([int(ptav['value']) for ptav in no_variant_attribute_values])
			received_combination = product.product_template_attribute_value_ids | received_no_variant_values
			product_template = product.product_tmpl_id

			# handle all cases where incorrect or incomplete data are received
			combination = product_template._get_closest_possible_combination(received_combination)

			# get or create (if dynamic) the correct variant
			product = product_template._create_product_variant(combination)

			if not product:
				raise UserError(_("The given combination does not exist therefore it cannot be added to cart."))

			product_id = product.id

			values = self._website_product_id_change(self.id, product_id, qty=1)

			# add no_variant attributes that were not received
			for ptav in combination.filtered(lambda ptav: ptav.attribute_id.create_variant == 'no_variant' and ptav not in received_no_variant_values):
				no_variant_attribute_values.append({
					'value': ptav.id,
				})

			# save no_variant attributes values
			if no_variant_attribute_values:
				values['product_no_variant_attribute_value_ids'] = [
					(6, 0, [int(attribute['value']) for attribute in no_variant_attribute_values])
				]

			# add is_custom attribute values that were not received
			custom_values = kwargs.get('product_custom_attribute_values') or []
			received_custom_values = product.env['product.template.attribute.value'].browse([int(ptav['custom_product_template_attribute_value_id']) for ptav in custom_values])

			for ptav in combination.filtered(lambda ptav: ptav.is_custom and ptav not in received_custom_values):
				custom_values.append({
					'custom_product_template_attribute_value_id': ptav.id,
					'custom_value': '',
				})

			# save is_custom attributes values
			if custom_values:
				values['product_custom_attribute_value_ids'] = [(0, 0, {
					'custom_product_template_attribute_value_id': custom_value['custom_product_template_attribute_value_id'],
					'custom_value': custom_value['custom_value']
				}) for custom_value in custom_values]

			# create the line
			order_line = SaleOrderLineSudo.create(values)
			if 'product_uom_id' in kwargs:
				order_line.product_uom = int(kwargs['product_uom_id'])
				order_line.product_uom_change()
				
			print (order_line, values, '\n  \n\n OLOLOLOLOLOLOLOLOL........................')

			try:
				order_line._compute_tax_id()
			except ValidationError as e:
				# The validation may occur in backend (eg: taxcloud) but should fail silently in frontend
				_logger.debug("ValidationError occurs during tax compute. %s" % (e))
			if add_qty:
				add_qty -= 1

		# compute new quantity
		if set_qty:
			quantity = set_qty
		elif add_qty is not None:
			quantity = order_line.product_uom_qty + (add_qty or 0)

		# Remove zero of negative lines
		if quantity <= 0:
			linked_line = order_line.linked_line_id
			order_line.unlink()
			if linked_line:
				# update description of the parent
				linked_product = product_with_context.browse(linked_line.product_id.id)
				linked_line.name = linked_line.get_sale_order_line_multiline_description_sale(linked_product)
		else:
			# update line
			no_variant_attributes_price_extra = [ptav.price_extra for ptav in order_line.product_no_variant_attribute_value_ids]
			values = self.with_context(no_variant_attributes_price_extra=tuple(no_variant_attributes_price_extra))._website_product_id_change(self.id, product_id, qty=quantity)
			if self.pricelist_id.discount_policy == 'with_discount' and not self.env.context.get('fixed_price'):
				order = self.sudo().browse(self.id)
				product_context.update({
					'partner': order.partner_id,
					'quantity': quantity,
					'date': order.date_order,
					'pricelist': order.pricelist_id.id,
					'force_company': order.company_id.id,
				})
				product_with_context = self.env['product.product'].with_context(product_context)
				product = product_with_context.browse(product_id)
				values['price_unit'] = self.env['account.tax']._fix_tax_included_price_company(
					order_line._get_display_price(product),
					order_line.product_id.taxes_id,
					order_line.tax_id,
					self.company_id
				)
				
			
			
				
			if 'product_uom_id' in kwargs:
				values.update({'product_uom': int(kwargs['product_uom_id'])})
			else:
				del values['product_uom']
				
			order_line.write(values)
			order_line.product_uom_change()
				
				

			# link a product to the sales order
			if kwargs.get('linked_line_id'):
				linked_line = SaleOrderLineSudo.browse(kwargs['linked_line_id'])
				order_line.write({
					'linked_line_id': linked_line.id,
				})
				linked_product = product_with_context.browse(linked_line.product_id.id)
				linked_line.name = linked_line.get_sale_order_line_multiline_description_sale(linked_product)
			# Generate the description with everything. This is done after
			# creating because the following related fields have to be set:
			# - product_no_variant_attribute_value_ids
			# - product_custom_attribute_value_ids
			# - linked_line_id
			order_line.name = order_line.get_sale_order_line_multiline_description_sale(product)

		option_lines = self.order_line.filtered(lambda l: l.linked_line_id.id == order_line.id)

		return {'line_id': order_line.id, 'quantity': quantity, 'option_ids': list(set(option_lines.ids))}
	
	
	
	
SaleOrder._cart_update = _cart_update
		
		
		
		
		

class product(models.Model):
	
	_inherit = 'product.template'
	
	
	extra_units = fields.Many2many('uom.uom', 'product_id', 'uom_id', 'prod_uom_rel', string="Extra Units")
	
	def units_web(self):
		
		product = self.env['product.template'].sudo().browse(self.id)
		units = [product.uom_id]
		for item in product.extra_units:
			units.append(item)
			
		return units
		