# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RentUtilityType(models.Model):
    _name = 'rent.utility.type'
    _description = 'Rent Utility Type'
    _order = 'name'

    name = fields.Char(required=True)
    product_id = fields.Many2one(
        'product.product', string='Service Product', required=True,
        domain=[('type', '=', 'service')]
    )
    pricing = fields.Selection(
        [('fixed', 'Fixed per Period'),
         ('meter', 'Per Unit (Meter Reading)')],
        default='meter', required=True
    )
    unit_rate = fields.Float(
        string='Default Unit Rate',
        help="For meter pricing: price per unit (e.g., per kWh / per m³).\n"
             "For fixed pricing: default amount per period."
    )
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')

class RentUtilityExpense(models.Model):
    _name = 'rent.utility.expense'
    _description = 'Rent Utility Expense'
    _order = 'period_start desc, id desc'

    name = fields.Char(default=lambda s: _('Utility'), required=True)
    contract_id = fields.Many2one('rent.contract', required=True, ondelete='cascade')
    type_id = fields.Many2one('rent.utility.type', required=True)
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)

    type_pricing = fields.Selection(related='type_id.pricing', store=False, readonly=True)
    
    # Metering
    reading_start = fields.Float()
    reading_end = fields.Float()
    units = fields.Float(compute='_compute_units', store=True)
    unit_rate = fields.Float(help="Override the default rate if needed.")
    amount = fields.Monetary(currency_field='currency_id', required=True)
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id.id, required=True
    )

    invoice_id = fields.Many2one('account.move', domain=[('move_type', '=', 'out_invoice')])
    move_line_id = fields.Many2one('account.move.line')  # optional bookmark for the exact line
    state = fields.Selection(
        [('draft', 'Draft'), ('billed', 'Billed'), ('paid', 'Paid')],
        compute='_compute_state', store=True, default='draft'
    )
    notes = fields.Char()

    @api.depends('reading_start', 'reading_end', 'type_id.pricing')
    def _compute_units(self):
        for rec in self:
            if rec.type_id and rec.type_id.pricing == 'meter':
                rec.units = max((rec.reading_end or 0.0) - (rec.reading_start or 0.0), 0.0)
            else:
                rec.units = 1.0

    @api.onchange('type_id')
    def _onchange_type(self):
        for rec in self:
            if rec.type_id:
                rec.unit_rate = rec.type_id.unit_rate
                # default amount guess
                if rec.type_id.pricing == 'fixed':
                    rec.amount = rec.type_id.unit_rate
                elif rec.type_id.pricing == 'meter':
                    rec.amount = rec.units * (rec.unit_rate or 0.0)

    @api.onchange('units', 'unit_rate', 'type_id')
    def _onchange_amount_from_units(self):
        for rec in self:
            if rec.type_id and rec.type_id.pricing == 'meter':
                rec.amount = (rec.units or 0.0) * (rec.unit_rate or 0.0)

    @api.depends('invoice_id.payment_state')
    def _compute_state(self):
        for rec in self:
            if not rec.invoice_id:
                rec.state = 'draft'
            else:
                if rec.invoice_id.payment_state == 'paid':
                    rec.state = 'paid'
                else:
                    rec.state = 'billed'


