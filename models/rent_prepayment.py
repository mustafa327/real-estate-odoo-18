# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, date as pydate
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class RentPrepayment(models.Model):
    _name = 'rent.prepayment'
    _description = "Rent Prepayment / دفعة مقدّمة"
    _order = 'date desc, id desc'

    contract_id = fields.Many2one('rent.contract', required=True, ondelete='cascade')
    date = fields.Date(default=fields.Date.context_today, required=True)
    months = fields.Integer(string="Months Covered", default=1)
    amount = fields.Monetary(string="Amount", required=True)
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id.id
    )
    description = fields.Char(string="Description", default="Advance payment")
    move_id = fields.Many2one('account.move', string="Prepayment Invoice")
    amount_consumed = fields.Monetary(string="Consumed", compute='_compute_consumed', store=True)
    balance = fields.Monetary(string="Remaining", compute='_compute_consumed', store=True)

    @api.constrains('amount', 'months')
    def _check_positive(self):
        for rec in self:
            if rec.amount <= 0 or rec.months <= 0:
                raise ValidationError(_("Amount and Months must be positive."))

    @api.depends('amount', 'contract_id.prepayment_consumption_ids.prepayment_id', 'contract_id.prepayment_consumption_ids.amount')
    def _compute_consumed(self):
        for rec in self:
            consumed = sum(rec.contract_id.prepayment_consumption_ids.filtered(lambda c: c.prepayment_id == rec).mapped('amount'))
            rec.amount_consumed = consumed
            rec.balance = rec.amount - consumed


class RentPrepaymentConsumption(models.Model):
    _name = 'rent.prepayment.consumption'
    _description = "Prepayment Consumption Link"

    contract_id = fields.Many2one('rent.contract', required=True, ondelete='cascade')
    invoice_id = fields.Many2one('account.move', required=True)
    prepayment_id = fields.Many2one('rent.prepayment', required=True)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related='prepayment_id.currency_id', store=True)


class RentContract(models.Model):
    _inherit = 'rent.contract'

    prepayment_ids = fields.One2many('rent.prepayment', 'contract_id', string="Advance Payments")
    prepayment_consumption_ids = fields.One2many('rent.prepayment.consumption', 'contract_id', string="Advance Consumptions")

    def _get_prepayment_balance(self):
        self.ensure_one()
        total = sum(self.prepayment_ids.mapped('amount'))
        consumed = sum(self.prepayment_ids.mapped('amount_consumed'))
        return total - consumed

    def _apply_prepayment_to_invoice(self, invoice):
        """Reduce invoice with available prepayment. Adds a negative line and records a consumption link."""
        self.ensure_one()
        if invoice.move_type != 'out_invoice':
            return

        balance = self._get_prepayment_balance()
        if balance <= 0:
            return

        # Amount to cover (tax excluded or included? We use untaxed for simplicity; adjust if needed)
        to_cover = min(balance, abs(invoice.amount_total))
        if not to_cover:
            return

        product = self.env.ref('product.product_product_consumable', raise_if_not_found=False)
        invoice.write({
            'invoice_line_ids': [(0, 0, {
                'name': _('Advance Payment Consumption / استهلاك دفعة مقدّمة'),
                'quantity': 1.0,
                'price_unit': -to_cover,  
                'product_id': product.id if product else False,
                'tax_ids': False,         
            })]
        })

        if hasattr(invoice, '_onchange_invoice_line_ids'):
            invoice._onchange_invoice_line_ids()

        # Record consumption split across prepayments (FIFO)
        remaining = to_cover
        for prepay in self.prepayment_ids.sorted('date'):
            if remaining <= 0:
                break
            avail = prepay.balance
            if avail <= 0:
                continue
            consume_now = min(avail, remaining)
            self.env['rent.prepayment.consumption'].create({
                'contract_id': self.id,
                'invoice_id': invoice.id,
                'prepayment_id': prepay.id,
                'amount': consume_now,
            })
            remaining -= consume_now

        # done
        return True

    def _month_bounds(self, day):
        """Return (first_day, last_day) for the month of 'day' (python date)."""
        first = day.replace(day=1)
        last = (first + relativedelta(months=1)) - timedelta(days=1)
        return first, last

    def _find_month_invoice(self, on_date):
        """Find the draft/posted invoice of this contract for the month of on_date."""
        self.ensure_one()
        first, last = self._month_bounds(on_date)
        return self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('partner_id', '=', self.partner_id.id),
            ('x_building_id', '=', self.building_id.id),
            ('x_unit_id', '=', self.unit_id.id),
            ('invoice_date', '>=', first),
            ('invoice_date', '<=', last),
        ], order='id desc', limit=1)

    def _ensure_month_invoice(self, on_date):
        """Return a draft invoice for the period; create one if missing (with your tags & owner)."""
        self.ensure_one()
        inv = self._find_month_invoice(on_date)
        if inv and inv.state == 'draft':
            return inv
        if inv and inv.state == 'posted':
            # already billed this month → nothing to create
            return inv

        # create a new draft using your existing builder but with invoice_date = on_date
        vals = self._prepare_invoice_vals()
        vals['invoice_date'] = on_date
        return self.env['account.move'].create(vals)
    

    @api.model
    def cron_consume_prepayments_daily(self):
        """Daily: for contracts due today, create/find the month invoice and consume prepayment."""
        today = fields.Date.context_today(self)
        domain = [
            ('state', '=', 'active'),
            '|', ('start_date', '=', False), ('start_date', '<=', today),
            '|', ('end_date',   '=', False), ('end_date',   '>=', today),
            ('rent_due_day', '=', today.day),
            '|', ('last_due_activity_date', '=', False), ('last_due_activity_date', '<', today),
        ]
        contracts = self.search(domain)
        if not contracts:
            return

        todo_type = self.env.ref('mail.mail_activity_data_todo')
        for c in contracts:
            inv = c._ensure_month_invoice(today)

            # avoid double-consuming if this cron runs again
            already_consumed = bool(self.env['rent.prepayment.consumption'].search_count([('invoice_id', '=', inv.id)]))
            if inv.state == 'draft' and not already_consumed:
                # apply prepayment (adds negative line + FIFO links)
                c._apply_prepayment_to_invoice(inv)

                # recompute totals if onchange hook exists (you’re on 18; safe fallback)
                if hasattr(inv, '_onchange_invoice_line_ids'):
                    inv._onchange_invoice_line_ids()

                # post if fully covered → becomes paid at 0 total
                if inv.amount_total == 0 and hasattr(inv, 'action_post'):
                    inv.action_post()

            # stamp the date so we don’t create duplicate reminders today
            c.last_due_activity_date = today

            # if there’s uncovered remainder, create a reminder to collect it
            monthly_due = c.amount if c.recurrence == 'month' else (c.amount / 12.0)
            prepay_bal = c._get_prepayment_balance() if hasattr(c, '_get_prepayment_balance') else 0.0

            # Consider remainder after consumption (if draft, use its current total; if posted, use residual)
            remainder = inv.amount_residual if inv.state == 'posted' else inv.amount_total
            if remainder and remainder > 0:
                c.activity_schedule(
                    activity_type_id=todo_type.id,
                    date_deadline=today,
                    user_id=c.responsible_id.id or self.env.user.id,
                    summary=_('Collect Rent (Uncovered Amount)'),
                    note=_('Remaining amount for %s: %.2f') % (c.name, remainder),
                )