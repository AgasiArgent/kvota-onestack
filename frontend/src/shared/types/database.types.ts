export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  kvota: {
    Tables: {
      approvals: {
        Row: {
          id: string
          quote_id: string
          requested_by: string
          approver_id: string
          approval_type: string
          reason: string
          status: string
          decision_comment: string | null
          requested_at: string
          decided_at: string | null
          modifications: Json | null
        }
        Insert: {
          id?: string
          quote_id: string
          requested_by: string
          approver_id: string
          approval_type?: string
          reason: string
          status?: string
          decision_comment?: string | null
          requested_at?: string
          decided_at?: string | null
          modifications?: Json | null
        }
        Update: {
          id?: string
          quote_id?: string
          requested_by?: string
          approver_id?: string
          approval_type?: string
          reason?: string
          status?: string
          decision_comment?: string | null
          requested_at?: string
          decided_at?: string | null
          modifications?: Json | null
        }
        Relationships: []
      }
      bank_accounts: {
        Row: {
          id: string
          organization_id: string
          entity_type: string
          entity_id: string
          bank_name: string
          account_number: string
          bik: string | null
          correspondent_account: string | null
          swift: string | null
          iban: string | null
          currency: string
          is_default: boolean
          is_active: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          organization_id: string
          entity_type: string
          entity_id: string
          bank_name: string
          account_number: string
          bik?: string | null
          correspondent_account?: string | null
          swift?: string | null
          iban?: string | null
          currency?: string
          is_default?: boolean
          is_active?: boolean
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          organization_id?: string
          entity_type?: string
          entity_id?: string
          bank_name?: string
          account_number?: string
          bik?: string | null
          correspondent_account?: string | null
          swift?: string | null
          iban?: string | null
          currency?: string
          is_default?: boolean
          is_active?: boolean
          created_at?: string
          updated_at?: string
        }
        Relationships: []
      }
      brand_assignments: {
        Row: {
          id: string
          organization_id: string
          brand: string
          user_id: string
          created_at: string | null
          created_by: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          brand: string
          user_id: string
          created_at?: string | null
          created_by?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          brand?: string
          user_id?: string
          created_at?: string | null
          created_by?: string | null
        }
        Relationships: []
      }
      brand_supplier_assignments: {
        Row: {
          id: string
          organization_id: string
          brand: string
          supplier_id: string
          is_primary: boolean | null
          notes: string | null
          created_at: string | null
          updated_at: string | null
          created_by: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          brand: string
          supplier_id: string
          is_primary?: boolean | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
          created_by?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          brand?: string
          supplier_id?: string
          is_primary?: boolean | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
          created_by?: string | null
        }
        Relationships: []
      }
      buyer_companies: {
        Row: {
          id: string
          organization_id: string
          name: string
          company_code: string
          country: string | null
          inn: string | null
          kpp: string | null
          ogrn: string | null
          registration_address: string | null
          general_director_name: string | null
          general_director_position: string | null
          is_active: boolean | null
          created_at: string | null
          updated_at: string | null
          created_by: string | null
          region: string | null
          legal_name: string | null
          tax_id: string | null
          address: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          name: string
          company_code: string
          country?: string | null
          inn?: string | null
          kpp?: string | null
          ogrn?: string | null
          registration_address?: string | null
          general_director_name?: string | null
          general_director_position?: string | null
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          created_by?: string | null
          region?: string | null
          legal_name?: string | null
          tax_id?: string | null
          address?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          name?: string
          company_code?: string
          country?: string | null
          inn?: string | null
          kpp?: string | null
          ogrn?: string | null
          registration_address?: string | null
          general_director_name?: string | null
          general_director_position?: string | null
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          created_by?: string | null
          region?: string | null
          legal_name?: string | null
          tax_id?: string | null
          address?: string | null
        }
        Relationships: []
      }
      calculation_settings: {
        Row: {
          id: string
          organization_id: string
          rate_forex_risk: number
          rate_fin_comm: number
          rate_loan_interest_daily: number
          created_at: string | null
          updated_at: string | null
          updated_by: string | null
          rate_loan_interest_annual: number | null
          customs_logistics_pmt_due: number | null
          tax_rate_turkey: number | null
          tax_rate_russia: number | null
          use_manual_exchange_rates: boolean
          default_input_currency: string
        }
        Insert: {
          id?: string
          organization_id: string
          rate_forex_risk?: number
          rate_fin_comm?: number
          rate_loan_interest_daily?: number
          created_at?: string | null
          updated_at?: string | null
          updated_by?: string | null
          rate_loan_interest_annual?: number | null
          customs_logistics_pmt_due?: number | null
          tax_rate_turkey?: number | null
          tax_rate_russia?: number | null
          use_manual_exchange_rates?: boolean
          default_input_currency?: string
        }
        Update: {
          id?: string
          organization_id?: string
          rate_forex_risk?: number
          rate_fin_comm?: number
          rate_loan_interest_daily?: number
          created_at?: string | null
          updated_at?: string | null
          updated_by?: string | null
          rate_loan_interest_annual?: number | null
          customs_logistics_pmt_due?: number | null
          tax_rate_turkey?: number | null
          tax_rate_russia?: number | null
          use_manual_exchange_rates?: boolean
          default_input_currency?: string
        }
        Relationships: []
      }
      calls: {
        Row: {
          id: string
          organization_id: string
          customer_id: string
          contact_person_id: string | null
          user_id: string
          call_type: string
          call_category: string | null
          scheduled_date: string | null
          comment: string | null
          customer_needs: string | null
          meeting_notes: string | null
          created_at: string | null
          updated_at: string | null
          assigned_to: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          customer_id: string
          contact_person_id?: string | null
          user_id: string
          call_type?: string
          call_category?: string | null
          scheduled_date?: string | null
          comment?: string | null
          customer_needs?: string | null
          meeting_notes?: string | null
          created_at?: string | null
          updated_at?: string | null
          assigned_to?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          customer_id?: string
          contact_person_id?: string | null
          user_id?: string
          call_type?: string
          call_category?: string | null
          scheduled_date?: string | null
          comment?: string | null
          customer_needs?: string | null
          meeting_notes?: string | null
          created_at?: string | null
          updated_at?: string | null
          assigned_to?: string | null
        }
        Relationships: []
      }
      changelog_reads: {
        Row: {
          user_id: string
          last_read_date: string
          last_read_at: string
        }
        Insert: {
          user_id: string
          last_read_date?: string
          last_read_at?: string
        }
        Update: {
          user_id?: string
          last_read_date?: string
          last_read_at?: string
        }
        Relationships: []
      }
      currency_contracts: {
        Row: {
          id: string
          organization_id: string
          seller_entity_type: string | null
          seller_entity_id: string | null
          buyer_entity_type: string | null
          buyer_entity_id: string | null
          currency: string
          contract_number: string
          contract_date: string | null
          is_active: boolean
          notes: string | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          seller_entity_type?: string | null
          seller_entity_id?: string | null
          buyer_entity_type?: string | null
          buyer_entity_id?: string | null
          currency?: string
          contract_number: string
          contract_date?: string | null
          is_active?: boolean
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          seller_entity_type?: string | null
          seller_entity_id?: string | null
          buyer_entity_type?: string | null
          buyer_entity_id?: string | null
          currency?: string
          contract_number?: string
          contract_date?: string | null
          is_active?: boolean
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      currency_invoice_items: {
        Row: {
          id: string
          currency_invoice_id: string
          source_item_id: string | null
          product_name: string
          sku: string | null
          idn_sku: string | null
          manufacturer: string | null
          quantity: number
          unit: string | null
          hs_code: string | null
          base_price: number
          price: number
          total: number
          sort_order: number | null
          created_at: string | null
        }
        Insert: {
          id?: string
          currency_invoice_id: string
          source_item_id?: string | null
          product_name: string
          sku?: string | null
          idn_sku?: string | null
          manufacturer?: string | null
          quantity?: number
          unit?: string | null
          hs_code?: string | null
          base_price?: number
          price?: number
          total?: number
          sort_order?: number | null
          created_at?: string | null
        }
        Update: {
          id?: string
          currency_invoice_id?: string
          source_item_id?: string | null
          product_name?: string
          sku?: string | null
          idn_sku?: string | null
          manufacturer?: string | null
          quantity?: number
          unit?: string | null
          hs_code?: string | null
          base_price?: number
          price?: number
          total?: number
          sort_order?: number | null
          created_at?: string | null
        }
        Relationships: []
      }
      currency_invoices: {
        Row: {
          id: string
          deal_id: string
          segment: string
          invoice_number: string
          seller_entity_type: string | null
          seller_entity_id: string | null
          buyer_entity_type: string | null
          buyer_entity_id: string | null
          markup_percent: number
          total_amount: number | null
          currency: string
          status: string
          source_invoice_ids: Json | null
          generated_at: string | null
          verified_by: string | null
          verified_at: string | null
          organization_id: string
          created_at: string | null
          updated_at: string | null
          seller_bank_account_id: string | null
          contract_number: string | null
          contract_date: string | null
          payment_terms: string | null
          delivery_terms: string | null
        }
        Insert: {
          id?: string
          deal_id: string
          segment: string
          invoice_number: string
          seller_entity_type?: string | null
          seller_entity_id?: string | null
          buyer_entity_type?: string | null
          buyer_entity_id?: string | null
          markup_percent?: number
          total_amount?: number | null
          currency?: string
          status?: string
          source_invoice_ids?: Json | null
          generated_at?: string | null
          verified_by?: string | null
          verified_at?: string | null
          organization_id: string
          created_at?: string | null
          updated_at?: string | null
          seller_bank_account_id?: string | null
          contract_number?: string | null
          contract_date?: string | null
          payment_terms?: string | null
          delivery_terms?: string | null
        }
        Update: {
          id?: string
          deal_id?: string
          segment?: string
          invoice_number?: string
          seller_entity_type?: string | null
          seller_entity_id?: string | null
          buyer_entity_type?: string | null
          buyer_entity_id?: string | null
          markup_percent?: number
          total_amount?: number | null
          currency?: string
          status?: string
          source_invoice_ids?: Json | null
          generated_at?: string | null
          verified_by?: string | null
          verified_at?: string | null
          organization_id?: string
          created_at?: string | null
          updated_at?: string | null
          seller_bank_account_id?: string | null
          contract_number?: string | null
          contract_date?: string | null
          payment_terms?: string | null
          delivery_terms?: string | null
        }
        Relationships: []
      }
      customer_assignees: {
        Row: {
          customer_id: string
          user_id: string
          created_at: string
          created_by: string | null
        }
        Insert: {
          customer_id: string
          user_id: string
          created_at?: string
          created_by?: string | null
        }
        Update: {
          customer_id?: string
          user_id?: string
          created_at?: string
          created_by?: string | null
        }
        Relationships: []
      }
      customer_contacts: {
        Row: {
          id: string
          customer_id: string
          name: string
          phone: string | null
          email: string | null
          position: string | null
          is_primary: boolean | null
          notes: string | null
          created_at: string | null
          updated_at: string | null
          organization_id: string
          last_name: string | null
          is_signatory: boolean | null
          signatory_position: string | null
          patronymic: string | null
          is_lpr: boolean | null
          phones: Json | null
        }
        Insert: {
          id?: string
          customer_id: string
          name: string
          phone?: string | null
          email?: string | null
          position?: string | null
          is_primary?: boolean | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
          organization_id: string
          last_name?: string | null
          is_signatory?: boolean | null
          signatory_position?: string | null
          patronymic?: string | null
          is_lpr?: boolean | null
          phones?: Json | null
        }
        Update: {
          id?: string
          customer_id?: string
          name?: string
          phone?: string | null
          email?: string | null
          position?: string | null
          is_primary?: boolean | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
          organization_id?: string
          last_name?: string | null
          is_signatory?: boolean | null
          signatory_position?: string | null
          patronymic?: string | null
          is_lpr?: boolean | null
          phones?: Json | null
        }
        Relationships: []
      }
      customer_contracts: {
        Row: {
          id: string
          organization_id: string
          customer_id: string
          contract_number: string
          contract_date: string
          status: string
          next_specification_number: number
          notes: string | null
          created_at: string
          updated_at: string
          created_by: string | null
          contract_type: string | null
          end_date: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          customer_id: string
          contract_number: string
          contract_date: string
          status?: string
          next_specification_number?: number
          notes?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
          contract_type?: string | null
          end_date?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          customer_id?: string
          contract_number?: string
          contract_date?: string
          status?: string
          next_specification_number?: number
          notes?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
          contract_type?: string | null
          end_date?: string | null
        }
        Relationships: []
      }
      customer_delivery_addresses: {
        Row: {
          id: string
          customer_id: string
          organization_id: string
          address: string
          name: string | null
          is_default: boolean | null
          notes: string | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          customer_id: string
          organization_id: string
          address: string
          name?: string | null
          is_default?: boolean | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          customer_id?: string
          organization_id?: string
          address?: string
          name?: string | null
          is_default?: boolean | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      customers: {
        Row: {
          id: string
          organization_id: string
          name: string
          email: string | null
          phone: string | null
          address: string | null
          city: string | null
          region: string | null
          country: string | null
          postal_code: string | null
          inn: string | null
          kpp: string | null
          ogrn: string | null
          company_type: string | null
          industry: string | null
          credit_limit: number | null
          payment_terms: number | null
          status: string | null
          notes: string | null
          created_at: string
          updated_at: string
          created_by: string | null
          qualified_from_lead_id: string | null
          warehouse_addresses: Json | null
          general_director_name: string | null
          general_director_position: string | null
          legal_address: string | null
          actual_address: string | null
          postal_address: string | null
          order_source: string | null
          manager_id: string | null
          general_email: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          name: string
          email?: string | null
          phone?: string | null
          address?: string | null
          city?: string | null
          region?: string | null
          country?: string | null
          postal_code?: string | null
          inn?: string | null
          kpp?: string | null
          ogrn?: string | null
          company_type?: string | null
          industry?: string | null
          credit_limit?: number | null
          payment_terms?: number | null
          status?: string | null
          notes?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
          qualified_from_lead_id?: string | null
          warehouse_addresses?: Json | null
          general_director_name?: string | null
          general_director_position?: string | null
          legal_address?: string | null
          actual_address?: string | null
          postal_address?: string | null
          order_source?: string | null
          manager_id?: string | null
          general_email?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          name?: string
          email?: string | null
          phone?: string | null
          address?: string | null
          city?: string | null
          region?: string | null
          country?: string | null
          postal_code?: string | null
          inn?: string | null
          kpp?: string | null
          ogrn?: string | null
          company_type?: string | null
          industry?: string | null
          credit_limit?: number | null
          payment_terms?: number | null
          status?: string | null
          notes?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
          qualified_from_lead_id?: string | null
          warehouse_addresses?: Json | null
          general_director_name?: string | null
          general_director_position?: string | null
          legal_address?: string | null
          actual_address?: string | null
          postal_address?: string | null
          order_source?: string | null
          manager_id?: string | null
          general_email?: string | null
        }
        Relationships: []
      }
      customs_declaration_items: {
        Row: {
          id: string
          declaration_id: string
          block_number: number | null
          item_number: number | null
          sku: string | null
          description: string | null
          manufacturer: string | null
          brand: string | null
          quantity: number | null
          unit: string | null
          gross_weight_kg: number | null
          net_weight_kg: number | null
          invoice_cost: number | null
          invoice_currency: string | null
          hs_code: string | null
          customs_value_rub: number | null
          fee_amount_rub: number | null
          duty_amount_rub: number | null
          vat_amount_rub: number | null
          deal_id: string | null
          matched_at: string | null
          organization_id: string
          created_at: string | null
        }
        Insert: {
          id?: string
          declaration_id: string
          block_number?: number | null
          item_number?: number | null
          sku?: string | null
          description?: string | null
          manufacturer?: string | null
          brand?: string | null
          quantity?: number | null
          unit?: string | null
          gross_weight_kg?: number | null
          net_weight_kg?: number | null
          invoice_cost?: number | null
          invoice_currency?: string | null
          hs_code?: string | null
          customs_value_rub?: number | null
          fee_amount_rub?: number | null
          duty_amount_rub?: number | null
          vat_amount_rub?: number | null
          deal_id?: string | null
          matched_at?: string | null
          organization_id: string
          created_at?: string | null
        }
        Update: {
          id?: string
          declaration_id?: string
          block_number?: number | null
          item_number?: number | null
          sku?: string | null
          description?: string | null
          manufacturer?: string | null
          brand?: string | null
          quantity?: number | null
          unit?: string | null
          gross_weight_kg?: number | null
          net_weight_kg?: number | null
          invoice_cost?: number | null
          invoice_currency?: string | null
          hs_code?: string | null
          customs_value_rub?: number | null
          fee_amount_rub?: number | null
          duty_amount_rub?: number | null
          vat_amount_rub?: number | null
          deal_id?: string | null
          matched_at?: string | null
          organization_id?: string
          created_at?: string | null
        }
        Relationships: []
      }
      customs_declarations: {
        Row: {
          id: string
          regnum: string
          declaration_date: string | null
          currency: string | null
          exchange_rate: number | null
          sender_name: string | null
          sender_country: string | null
          receiver_name: string | null
          receiver_inn: string | null
          internal_ref: string | null
          total_customs_value_rub: number | null
          total_fee_rub: number | null
          total_duty_rub: number | null
          total_vat_rub: number | null
          raw_xml: string | null
          created_by: string | null
          organization_id: string
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          regnum: string
          declaration_date?: string | null
          currency?: string | null
          exchange_rate?: number | null
          sender_name?: string | null
          sender_country?: string | null
          receiver_name?: string | null
          receiver_inn?: string | null
          internal_ref?: string | null
          total_customs_value_rub?: number | null
          total_fee_rub?: number | null
          total_duty_rub?: number | null
          total_vat_rub?: number | null
          raw_xml?: string | null
          created_by?: string | null
          organization_id: string
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          regnum?: string
          declaration_date?: string | null
          currency?: string | null
          exchange_rate?: number | null
          sender_name?: string | null
          sender_country?: string | null
          receiver_name?: string | null
          receiver_inn?: string | null
          internal_ref?: string | null
          total_customs_value_rub?: number | null
          total_fee_rub?: number | null
          total_duty_rub?: number | null
          total_vat_rub?: number | null
          raw_xml?: string | null
          created_by?: string | null
          organization_id?: string
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      deal_logistics_expenses: {
        Row: {
          id: string
          deal_id: string
          logistics_stage_id: string
          expense_subtype: string
          amount: number
          currency: string
          expense_date: string
          created_at: string | null
          description: string | null
          document_id: string | null
          created_by: string | null
          organization_id: string
        }
        Insert: {
          id?: string
          deal_id: string
          logistics_stage_id: string
          expense_subtype?: string
          amount: number
          currency?: string
          expense_date: string
          created_at?: string | null
          description?: string | null
          document_id?: string | null
          created_by?: string | null
          organization_id: string
        }
        Update: {
          id?: string
          deal_id?: string
          logistics_stage_id?: string
          expense_subtype?: string
          amount?: number
          currency?: string
          expense_date?: string
          created_at?: string | null
          description?: string | null
          document_id?: string | null
          created_by?: string | null
          organization_id?: string
        }
        Relationships: []
      }
      deals: {
        Row: {
          id: string
          specification_id: string
          quote_id: string
          organization_id: string
          deal_number: string
          signed_at: string
          total_amount: number
          currency: string
          status: string
          created_by: string | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          specification_id: string
          quote_id: string
          organization_id: string
          deal_number: string
          signed_at: string
          total_amount: number
          currency?: string
          status?: string
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          specification_id?: string
          quote_id?: string
          organization_id?: string
          deal_number?: string
          signed_at?: string
          total_amount?: number
          currency?: string
          status?: string
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      departments: {
        Row: {
          id: string
          name: string
          description: string | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          name: string
          description?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          name?: string
          description?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      documents: {
        Row: {
          id: string
          organization_id: string
          entity_type: string
          entity_id: string
          storage_path: string
          original_filename: string
          file_size_bytes: number | null
          mime_type: string | null
          document_type: string | null
          description: string | null
          uploaded_by: string | null
          created_at: string | null
          parent_quote_id: string | null
          comment_id: string | null
          status: string
        }
        Insert: {
          id?: string
          organization_id: string
          entity_type: string
          entity_id: string
          storage_path: string
          original_filename: string
          file_size_bytes?: number | null
          mime_type?: string | null
          document_type?: string | null
          description?: string | null
          uploaded_by?: string | null
          created_at?: string | null
          parent_quote_id?: string | null
          comment_id?: string | null
          status?: string
        }
        Update: {
          id?: string
          organization_id?: string
          entity_type?: string
          entity_id?: string
          storage_path?: string
          original_filename?: string
          file_size_bytes?: number | null
          mime_type?: string | null
          document_type?: string | null
          description?: string | null
          uploaded_by?: string | null
          created_at?: string | null
          parent_quote_id?: string | null
          comment_id?: string | null
          status?: string
        }
        Relationships: []
      }
      exchange_rates: {
        Row: {
          id: string
          from_currency: string
          to_currency: string
          rate: number
          source: string | null
          fetched_at: string
          created_at: string | null
        }
        Insert: {
          id?: string
          from_currency: string
          to_currency: string
          rate: number
          source?: string | null
          fetched_at: string
          created_at?: string | null
        }
        Update: {
          id?: string
          from_currency?: string
          to_currency?: string
          rate?: number
          source?: string | null
          fetched_at?: string
          created_at?: string | null
        }
        Relationships: []
      }
      invoice_cargo_places: {
        Row: {
          id: string
          invoice_id: string
          position: number
          weight_kg: number
          length_mm: number
          width_mm: number
          height_mm: number
          created_at: string
        }
        Insert: {
          id?: string
          invoice_id: string
          position?: number
          weight_kg: number
          length_mm: number
          width_mm: number
          height_mm: number
          created_at?: string
        }
        Update: {
          id?: string
          invoice_id?: string
          position?: number
          weight_kg?: number
          length_mm?: number
          width_mm?: number
          height_mm?: number
          created_at?: string
        }
        Relationships: []
      }
      invoice_item_prices: {
        Row: {
          id: string
          invoice_id: string
          quote_item_id: string
          organization_id: string
          purchase_price_original: number
          purchase_currency: string
          base_price_vat: number | null
          price_includes_vat: boolean
          production_time_days: number | null
          minimum_order_quantity: number | null
          supplier_notes: string | null
          version: number
          frozen_at: string | null
          frozen_by: string | null
          created_at: string
          updated_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          invoice_id: string
          quote_item_id: string
          organization_id: string
          purchase_price_original: number
          purchase_currency: string
          base_price_vat?: number | null
          price_includes_vat?: boolean
          production_time_days?: number | null
          minimum_order_quantity?: number | null
          supplier_notes?: string | null
          version?: number
          frozen_at?: string | null
          frozen_by?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          invoice_id?: string
          quote_item_id?: string
          organization_id?: string
          purchase_price_original?: number
          purchase_currency?: string
          base_price_vat?: number | null
          price_includes_vat?: boolean
          production_time_days?: number | null
          minimum_order_quantity?: number | null
          supplier_notes?: string | null
          version?: number
          frozen_at?: string | null
          frozen_by?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
        Relationships: []
      }
      invoice_letter_drafts: {
        Row: {
          id: string
          invoice_id: string
          created_by: string
          language: string
          method: string
          recipient_email: string | null
          subject: string | null
          body_text: string | null
          created_at: string
          updated_at: string
          sent_at: string | null
        }
        Insert: {
          id?: string
          invoice_id: string
          created_by: string
          language?: string
          method: string
          recipient_email?: string | null
          subject?: string | null
          body_text?: string | null
          created_at?: string
          updated_at?: string
          sent_at?: string | null
        }
        Update: {
          id?: string
          invoice_id?: string
          created_by?: string
          language?: string
          method?: string
          recipient_email?: string | null
          subject?: string | null
          body_text?: string | null
          created_at?: string
          updated_at?: string
          sent_at?: string | null
        }
        Relationships: []
      }
      invoices: {
        Row: {
          id: string
          quote_id: string
          supplier_id: string | null
          buyer_company_id: string | null
          pickup_location_id: string | null
          invoice_number: string
          currency: string
          total_weight_kg: number | null
          total_volume_m3: number | null
          created_at: string | null
          updated_at: string | null
          logistics_supplier_to_hub: number | null
          logistics_hub_to_customs: number | null
          logistics_customs_to_customer: number | null
          logistics_total_days: number | null
          logistics_notes: string | null
          logistics_completed_at: string | null
          logistics_completed_by: string | null
          logistics_supplier_to_hub_currency: string | null
          logistics_hub_to_customs_currency: string | null
          logistics_customs_to_customer_currency: string | null
          pickup_country: string | null
          status: string | null
          procurement_completed_at: string | null
          procurement_completed_by: string | null
          customs_completed_at: string | null
          customs_completed_by: string | null
          pickup_city: string | null
          assigned_logistics_user: string | null
          height_m: number | null
          length_m: number | null
          width_m: number | null
          package_count: number | null
          procurement_notes: string | null
          invoice_file_url: string | null
          verified_at: string | null
          verified_by: string | null
          pickup_country_code: string | null
          supplier_incoterms: string | null
          sent_at: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          supplier_id?: string | null
          buyer_company_id?: string | null
          pickup_location_id?: string | null
          invoice_number: string
          currency: string
          total_weight_kg?: number | null
          total_volume_m3?: number | null
          created_at?: string | null
          updated_at?: string | null
          logistics_supplier_to_hub?: number | null
          logistics_hub_to_customs?: number | null
          logistics_customs_to_customer?: number | null
          logistics_total_days?: number | null
          logistics_notes?: string | null
          logistics_completed_at?: string | null
          logistics_completed_by?: string | null
          logistics_supplier_to_hub_currency?: string | null
          logistics_hub_to_customs_currency?: string | null
          logistics_customs_to_customer_currency?: string | null
          pickup_country?: string | null
          status?: string | null
          procurement_completed_at?: string | null
          procurement_completed_by?: string | null
          customs_completed_at?: string | null
          customs_completed_by?: string | null
          pickup_city?: string | null
          assigned_logistics_user?: string | null
          height_m?: number | null
          length_m?: number | null
          width_m?: number | null
          package_count?: number | null
          procurement_notes?: string | null
          invoice_file_url?: string | null
          verified_at?: string | null
          verified_by?: string | null
          pickup_country_code?: string | null
          supplier_incoterms?: string | null
          sent_at?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          supplier_id?: string | null
          buyer_company_id?: string | null
          pickup_location_id?: string | null
          invoice_number?: string
          currency?: string
          total_weight_kg?: number | null
          total_volume_m3?: number | null
          created_at?: string | null
          updated_at?: string | null
          logistics_supplier_to_hub?: number | null
          logistics_hub_to_customs?: number | null
          logistics_customs_to_customer?: number | null
          logistics_total_days?: number | null
          logistics_notes?: string | null
          logistics_completed_at?: string | null
          logistics_completed_by?: string | null
          logistics_supplier_to_hub_currency?: string | null
          logistics_hub_to_customs_currency?: string | null
          logistics_customs_to_customer_currency?: string | null
          pickup_country?: string | null
          status?: string | null
          procurement_completed_at?: string | null
          procurement_completed_by?: string | null
          customs_completed_at?: string | null
          customs_completed_by?: string | null
          pickup_city?: string | null
          assigned_logistics_user?: string | null
          height_m?: number | null
          length_m?: number | null
          width_m?: number | null
          package_count?: number | null
          procurement_notes?: string | null
          invoice_file_url?: string | null
          verified_at?: string | null
          verified_by?: string | null
          pickup_country_code?: string | null
          supplier_incoterms?: string | null
          sent_at?: string | null
        }
        Relationships: []
      }
      item_price_offers: {
        Row: {
          id: string
          quote_item_id: string
          supplier_id: string
          organization_id: string
          price: number
          currency: string
          production_days: number | null
          is_selected: boolean | null
          notes: string | null
          created_at: string | null
          created_by: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          quote_item_id: string
          supplier_id: string
          organization_id: string
          price: number
          currency?: string
          production_days?: number | null
          is_selected?: boolean | null
          notes?: string | null
          created_at?: string | null
          created_by?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          quote_item_id?: string
          supplier_id?: string
          organization_id?: string
          price?: number
          currency?: string
          production_days?: number | null
          is_selected?: boolean | null
          notes?: string | null
          created_at?: string | null
          created_by?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      locations: {
        Row: {
          id: string
          organization_id: string
          country: string
          city: string | null
          code: string | null
          is_active: boolean | null
          created_at: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          country: string
          city?: string | null
          code?: string | null
          is_active?: boolean | null
          created_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          country?: string
          city?: string | null
          code?: string | null
          is_active?: boolean | null
          created_at?: string | null
        }
        Relationships: []
      }
      logistics_additional_expenses: {
        Row: {
          id: string
          invoice_id: string
          expense_type: string
          description: string | null
          amount: number
          currency: string
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          invoice_id: string
          expense_type: string
          description?: string | null
          amount?: number
          currency?: string
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          invoice_id?: string
          expense_type?: string
          description?: string | null
          amount?: number
          currency?: string
          created_at?: string
          updated_at?: string
        }
        Relationships: []
      }
      logistics_stages: {
        Row: {
          id: string
          deal_id: string
          stage_code: string
          status: string
          started_at: string | null
          completed_at: string | null
          responsible_person: string | null
          notes: string | null
          svh_id: string | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          deal_id: string
          stage_code: string
          status?: string
          started_at?: string | null
          completed_at?: string | null
          responsible_person?: string | null
          notes?: string | null
          svh_id?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          deal_id?: string
          stage_code?: string
          status?: string
          started_at?: string | null
          completed_at?: string | null
          responsible_person?: string | null
          notes?: string | null
          svh_id?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      migrations: {
        Row: {
          id: number
          filename: string
          applied_at: string | null
          checksum: string | null
        }
        Insert: {
          id?: number
          filename: string
          applied_at?: string | null
          checksum?: string | null
        }
        Update: {
          id?: number
          filename?: string
          applied_at?: string | null
          checksum?: string | null
        }
        Relationships: []
      }
      notifications: {
        Row: {
          id: string
          user_id: string
          quote_id: string | null
          deal_id: string | null
          type: string
          title: string
          message: string
          channel: string
          status: string
          telegram_message_id: number | null
          error_message: string | null
          sent_at: string | null
          read_at: string | null
          created_at: string
          organization_id: string | null
          specification_id: string | null
          approval_id: string | null
          priority: string | null
          metadata: Json | null
          expires_at: string | null
        }
        Insert: {
          id?: string
          user_id: string
          quote_id?: string | null
          deal_id?: string | null
          type: string
          title: string
          message: string
          channel?: string
          status?: string
          telegram_message_id?: number | null
          error_message?: string | null
          sent_at?: string | null
          read_at?: string | null
          created_at?: string
          organization_id?: string | null
          specification_id?: string | null
          approval_id?: string | null
          priority?: string | null
          metadata?: Json | null
          expires_at?: string | null
        }
        Update: {
          id?: string
          user_id?: string
          quote_id?: string | null
          deal_id?: string | null
          type?: string
          title?: string
          message?: string
          channel?: string
          status?: string
          telegram_message_id?: number | null
          error_message?: string | null
          sent_at?: string | null
          read_at?: string | null
          created_at?: string
          organization_id?: string | null
          specification_id?: string | null
          approval_id?: string | null
          priority?: string | null
          metadata?: Json | null
          expires_at?: string | null
        }
        Relationships: []
      }
      organization_currency_history: {
        Row: {
          id: string
          organization_id: string
          old_currency: string | null
          new_currency: string
          changed_by: string
          changed_at: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          old_currency?: string | null
          new_currency: string
          changed_by: string
          changed_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          old_currency?: string | null
          new_currency?: string
          changed_by?: string
          changed_at?: string | null
        }
        Relationships: []
      }
      organization_exchange_rates: {
        Row: {
          id: string
          organization_id: string
          from_currency: string
          to_currency: string
          rate: number
          source: string
          updated_by: string | null
          updated_at: string | null
          created_at: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          from_currency: string
          to_currency?: string
          rate: number
          source?: string
          updated_by?: string | null
          updated_at?: string | null
          created_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          from_currency?: string
          to_currency?: string
          rate?: number
          source?: string
          updated_by?: string | null
          updated_at?: string | null
          created_at?: string | null
        }
        Relationships: []
      }
      organization_invitations: {
        Row: {
          id: string
          organization_id: string
          role_id: string
          invited_by: string | null
          email: string
          token: string
          message: string | null
          status: string | null
          created_at: string | null
          expires_at: string | null
          accepted_at: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          role_id: string
          invited_by?: string | null
          email: string
          token: string
          message?: string | null
          status?: string | null
          created_at?: string | null
          expires_at?: string | null
          accepted_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          role_id?: string
          invited_by?: string | null
          email?: string
          token?: string
          message?: string | null
          status?: string | null
          created_at?: string | null
          expires_at?: string | null
          accepted_at?: string | null
        }
        Relationships: []
      }
      organization_members: {
        Row: {
          id: string
          organization_id: string
          user_id: string
          status: string | null
          is_owner: boolean | null
          invited_by: string | null
          invited_at: string | null
          joined_at: string | null
          created_at: string | null
          updated_at: string | null
          supervisor_id: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          user_id: string
          status?: string | null
          is_owner?: boolean | null
          invited_by?: string | null
          invited_at?: string | null
          joined_at?: string | null
          created_at?: string | null
          updated_at?: string | null
          supervisor_id?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          user_id?: string
          status?: string | null
          is_owner?: boolean | null
          invited_by?: string | null
          invited_at?: string | null
          joined_at?: string | null
          created_at?: string | null
          updated_at?: string | null
          supervisor_id?: string | null
        }
        Relationships: []
      }
      organization_workflow_settings: {
        Row: {
          organization_id: string
          workflow_mode: string
          financial_approval_threshold_usd: number | null
          senior_approval_threshold_usd: number | null
          multi_senior_threshold_usd: number | null
          board_approval_threshold_usd: number | null
          senior_approvals_required: number | null
          multi_senior_approvals_required: number | null
          board_approvals_required: number | null
          enable_parallel_logistics_customs: boolean | null
          allow_send_back: boolean | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          organization_id: string
          workflow_mode?: string
          financial_approval_threshold_usd?: number | null
          senior_approval_threshold_usd?: number | null
          multi_senior_threshold_usd?: number | null
          board_approval_threshold_usd?: number | null
          senior_approvals_required?: number | null
          multi_senior_approvals_required?: number | null
          board_approvals_required?: number | null
          enable_parallel_logistics_customs?: boolean | null
          allow_send_back?: boolean | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          organization_id?: string
          workflow_mode?: string
          financial_approval_threshold_usd?: number | null
          senior_approval_threshold_usd?: number | null
          multi_senior_threshold_usd?: number | null
          board_approval_threshold_usd?: number | null
          senior_approvals_required?: number | null
          multi_senior_approvals_required?: number | null
          board_approvals_required?: number | null
          enable_parallel_logistics_customs?: boolean | null
          allow_send_back?: boolean | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      organizations: {
        Row: {
          id: string
          name: string
          slug: string
          description: string | null
          logo_url: string | null
          status: string | null
          settings: Json | null
          subscription_tier: string | null
          subscription_expires_at: string | null
          created_at: string | null
          updated_at: string | null
          owner_id: string | null
          inn: string | null
          ceo_name: string | null
          ceo_title: string | null
          ceo_signature_url: string | null
          letter_template: string | null
          base_currency: string | null
          base_currency_updated_at: string | null
          financial_manager_id: string | null
          supplier_code: string | null
          kpp: string | null
          ogrn: string | null
          registration_address: string | null
          general_director_name: string | null
          general_director_position: string | null
          general_director_last_name: string | null
          general_director_first_name: string | null
          general_director_patronymic: string | null
          idn_counters: Json | null
        }
        Insert: {
          id?: string
          name: string
          slug: string
          description?: string | null
          logo_url?: string | null
          status?: string | null
          settings?: Json | null
          subscription_tier?: string | null
          subscription_expires_at?: string | null
          created_at?: string | null
          updated_at?: string | null
          owner_id?: string | null
          inn?: string | null
          ceo_name?: string | null
          ceo_title?: string | null
          ceo_signature_url?: string | null
          letter_template?: string | null
          base_currency?: string | null
          base_currency_updated_at?: string | null
          financial_manager_id?: string | null
          supplier_code?: string | null
          kpp?: string | null
          ogrn?: string | null
          registration_address?: string | null
          general_director_name?: string | null
          general_director_position?: string | null
          general_director_last_name?: string | null
          general_director_first_name?: string | null
          general_director_patronymic?: string | null
          idn_counters?: Json | null
        }
        Update: {
          id?: string
          name?: string
          slug?: string
          description?: string | null
          logo_url?: string | null
          status?: string | null
          settings?: Json | null
          subscription_tier?: string | null
          subscription_expires_at?: string | null
          created_at?: string | null
          updated_at?: string | null
          owner_id?: string | null
          inn?: string | null
          ceo_name?: string | null
          ceo_title?: string | null
          ceo_signature_url?: string | null
          letter_template?: string | null
          base_currency?: string | null
          base_currency_updated_at?: string | null
          financial_manager_id?: string | null
          supplier_code?: string | null
          kpp?: string | null
          ogrn?: string | null
          registration_address?: string | null
          general_director_name?: string | null
          general_director_position?: string | null
          general_director_last_name?: string | null
          general_director_first_name?: string | null
          general_director_patronymic?: string | null
          idn_counters?: Json | null
        }
        Relationships: []
      }
      payment_schedule: {
        Row: {
          id: string
          organization_id: string
          specification_id: string
          payment_number: number
          days_term: number | null
          calculation_variant: string | null
          expected_payment_date: string | null
          actual_payment_date: string | null
          payment_amount: number | null
          payment_currency: string | null
          payment_purpose: string | null
          payment_document_url: string | null
          comment: string | null
          created_by: string | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          specification_id: string
          payment_number: number
          days_term?: number | null
          calculation_variant?: string | null
          expected_payment_date?: string | null
          actual_payment_date?: string | null
          payment_amount?: number | null
          payment_currency?: string | null
          payment_purpose?: string | null
          payment_document_url?: string | null
          comment?: string | null
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          specification_id?: string
          payment_number?: number
          days_term?: number | null
          calculation_variant?: string | null
          expected_payment_date?: string | null
          actual_payment_date?: string | null
          payment_amount?: number | null
          payment_currency?: string | null
          payment_purpose?: string | null
          payment_document_url?: string | null
          comment?: string | null
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      phmb_brand_groups: {
        Row: {
          id: string
          org_id: string
          name: string
          brand_patterns: Json
          is_catchall: boolean
          sort_order: number
          created_at: string | null
        }
        Insert: {
          id?: string
          org_id: string
          name: string
          brand_patterns?: Json
          is_catchall?: boolean
          sort_order?: number
          created_at?: string | null
        }
        Update: {
          id?: string
          org_id?: string
          name?: string
          brand_patterns?: Json
          is_catchall?: boolean
          sort_order?: number
          created_at?: string | null
        }
        Relationships: []
      }
      phmb_brand_type_discounts: {
        Row: {
          id: string
          brand: string
          product_classification: string
          discount_pct: number
          org_id: string
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          brand: string
          product_classification?: string
          discount_pct?: number
          org_id: string
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          brand?: string
          product_classification?: string
          discount_pct?: number
          org_id?: string
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      phmb_price_list: {
        Row: {
          id: string
          cat_number: string
          product_name: string
          list_price_rmb: number
          brand: string
          product_classification: string
          vendor: string
          hs_code: string | null
          duty_pct: number | null
          delivery_days: number | null
          additional_fee_usd: number | null
          org_id: string
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          cat_number: string
          product_name: string
          list_price_rmb: number
          brand?: string
          product_classification?: string
          vendor?: string
          hs_code?: string | null
          duty_pct?: number | null
          delivery_days?: number | null
          additional_fee_usd?: number | null
          org_id: string
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          cat_number?: string
          product_name?: string
          list_price_rmb?: number
          brand?: string
          product_classification?: string
          vendor?: string
          hs_code?: string | null
          duty_pct?: number | null
          delivery_days?: number | null
          additional_fee_usd?: number | null
          org_id?: string
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      phmb_procurement_queue: {
        Row: {
          id: string
          org_id: string
          quote_item_id: string
          quote_id: string
          brand: string
          brand_group_id: string | null
          status: string
          priced_rmb: number | null
          notes: string | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          org_id: string
          quote_item_id: string
          quote_id: string
          brand?: string
          brand_group_id?: string | null
          status?: string
          priced_rmb?: number | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          org_id?: string
          quote_item_id?: string
          quote_id?: string
          brand?: string
          brand_group_id?: string | null
          status?: string
          priced_rmb?: number | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      phmb_quote_items: {
        Row: {
          id: string
          quote_id: string
          phmb_price_list_id: string | null
          cat_number: string
          product_name: string
          brand: string
          product_classification: string
          quantity: number
          list_price_rmb: number | null
          discount_pct: number
          exw_price_usd: number | null
          cogs_usd: number | null
          financial_cost_usd: number | null
          total_price_usd: number | null
          total_price_with_vat_usd: number | null
          hs_code: string | null
          duty_pct: number | null
          delivery_days: number | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          phmb_price_list_id?: string | null
          cat_number: string
          product_name: string
          brand?: string
          product_classification?: string
          quantity?: number
          list_price_rmb?: number | null
          discount_pct?: number
          exw_price_usd?: number | null
          cogs_usd?: number | null
          financial_cost_usd?: number | null
          total_price_usd?: number | null
          total_price_with_vat_usd?: number | null
          hs_code?: string | null
          duty_pct?: number | null
          delivery_days?: number | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          phmb_price_list_id?: string | null
          cat_number?: string
          product_name?: string
          brand?: string
          product_classification?: string
          quantity?: number
          list_price_rmb?: number | null
          discount_pct?: number
          exw_price_usd?: number | null
          cogs_usd?: number | null
          financial_cost_usd?: number | null
          total_price_usd?: number | null
          total_price_with_vat_usd?: number | null
          hs_code?: string | null
          duty_pct?: number | null
          delivery_days?: number | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      phmb_settings: {
        Row: {
          id: string
          org_id: string
          logistics_price_per_pallet: number
          base_price_per_pallet: number
          exchange_rate_insurance_pct: number
          financial_transit_pct: number
          customs_handling_cost: number
          customs_insurance_pct: number
          default_markup_pct: number
          default_advance_pct: number
          default_payment_days: number
          default_delivery_days: number
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          org_id: string
          logistics_price_per_pallet?: number
          base_price_per_pallet?: number
          exchange_rate_insurance_pct?: number
          financial_transit_pct?: number
          customs_handling_cost?: number
          customs_insurance_pct?: number
          default_markup_pct?: number
          default_advance_pct?: number
          default_payment_days?: number
          default_delivery_days?: number
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          org_id?: string
          logistics_price_per_pallet?: number
          base_price_per_pallet?: number
          exchange_rate_insurance_pct?: number
          financial_transit_pct?: number
          customs_handling_cost?: number
          customs_insurance_pct?: number
          default_markup_pct?: number
          default_advance_pct?: number
          default_payment_days?: number
          default_delivery_days?: number
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      phmb_versions: {
        Row: {
          id: string
          quote_id: string
          version_number: number
          label: string
          phmb_advance_pct: number
          phmb_payment_days: number
          phmb_markup_pct: number
          total_amount_usd: number | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          quote_id: string
          version_number?: number
          label?: string
          phmb_advance_pct?: number
          phmb_payment_days?: number
          phmb_markup_pct?: number
          total_amount_usd?: number | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          quote_id?: string
          version_number?: number
          label?: string
          phmb_advance_pct?: number
          phmb_payment_days?: number
          phmb_markup_pct?: number
          total_amount_usd?: number | null
          created_at?: string
          updated_at?: string
        }
        Relationships: []
      }
      plan_fact_categories: {
        Row: {
          id: string
          code: string
          name: string
          is_income: boolean
          sort_order: number
          created_at: string
        }
        Insert: {
          id?: string
          code: string
          name: string
          is_income?: boolean
          sort_order?: number
          created_at?: string
        }
        Update: {
          id?: string
          code?: string
          name?: string
          is_income?: boolean
          sort_order?: number
          created_at?: string
        }
        Relationships: []
      }
      plan_fact_financing_recalculated: {
        Row: {
          quote_id: string
          organization_id: string
          plan_stage1_days: number
          plan_stage2_days: number
          plan_total_financing_cost_quote_currency: number
          plan_total_financing_cost_org_currency: number
          fact_stage1_days: number | null
          fact_stage2_days: number | null
          fact_total_financing_cost_quote_currency: number | null
          fact_total_financing_cost_org_currency: number | null
          delta_days: number | null
          delta_financing_cost_quote_currency: number | null
          delta_financing_cost_org_currency: number | null
          extra_cost_from_delivery_delay_quote_currency: number | null
          extra_cost_from_delivery_delay_org_currency: number | null
          extra_cost_from_payment_delay_quote_currency: number | null
          extra_cost_from_payment_delay_org_currency: number | null
          recalculated_at: string | null
          timeline_snapshot: Json | null
        }
        Insert: {
          quote_id: string
          organization_id: string
          plan_stage1_days: number
          plan_stage2_days: number
          plan_total_financing_cost_quote_currency: number
          plan_total_financing_cost_org_currency: number
          fact_stage1_days?: number | null
          fact_stage2_days?: number | null
          fact_total_financing_cost_quote_currency?: number | null
          fact_total_financing_cost_org_currency?: number | null
          delta_days?: number | null
          delta_financing_cost_quote_currency?: number | null
          delta_financing_cost_org_currency?: number | null
          extra_cost_from_delivery_delay_quote_currency?: number | null
          extra_cost_from_delivery_delay_org_currency?: number | null
          extra_cost_from_payment_delay_quote_currency?: number | null
          extra_cost_from_payment_delay_org_currency?: number | null
          recalculated_at?: string | null
          timeline_snapshot?: Json | null
        }
        Update: {
          quote_id?: string
          organization_id?: string
          plan_stage1_days?: number
          plan_stage2_days?: number
          plan_total_financing_cost_quote_currency?: number
          plan_total_financing_cost_org_currency?: number
          fact_stage1_days?: number | null
          fact_stage2_days?: number | null
          fact_total_financing_cost_quote_currency?: number | null
          fact_total_financing_cost_org_currency?: number | null
          delta_days?: number | null
          delta_financing_cost_quote_currency?: number | null
          delta_financing_cost_org_currency?: number | null
          extra_cost_from_delivery_delay_quote_currency?: number | null
          extra_cost_from_delivery_delay_org_currency?: number | null
          extra_cost_from_payment_delay_quote_currency?: number | null
          extra_cost_from_payment_delay_org_currency?: number | null
          recalculated_at?: string | null
          timeline_snapshot?: Json | null
        }
        Relationships: []
      }
      plan_fact_items: {
        Row: {
          id: string
          deal_id: string
          category_id: string
          description: string | null
          planned_amount: number | null
          planned_currency: string | null
          planned_date: string | null
          actual_amount: number | null
          actual_currency: string | null
          actual_date: string | null
          actual_exchange_rate: number | null
          variance_amount: number | null
          payment_document: string | null
          notes: string | null
          created_by: string | null
          created_at: string | null
          updated_at: string | null
          logistics_stage_id: string | null
          attachment_url: string | null
        }
        Insert: {
          id?: string
          deal_id: string
          category_id: string
          description?: string | null
          planned_amount?: number | null
          planned_currency?: string | null
          planned_date?: string | null
          actual_amount?: number | null
          actual_currency?: string | null
          actual_date?: string | null
          actual_exchange_rate?: number | null
          variance_amount?: number | null
          payment_document?: string | null
          notes?: string | null
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
          logistics_stage_id?: string | null
          attachment_url?: string | null
        }
        Update: {
          id?: string
          deal_id?: string
          category_id?: string
          description?: string | null
          planned_amount?: number | null
          planned_currency?: string | null
          planned_date?: string | null
          actual_amount?: number | null
          actual_currency?: string | null
          actual_date?: string | null
          actual_exchange_rate?: number | null
          variance_amount?: number | null
          payment_document?: string | null
          notes?: string | null
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
          logistics_stage_id?: string | null
          attachment_url?: string | null
        }
        Relationships: []
      }
      plan_fact_permissions: {
        Row: {
          id: string
          role_id: string
          section_type: string
          can_edit: boolean
        }
        Insert: {
          id?: string
          role_id: string
          section_type: string
          can_edit?: boolean
        }
        Update: {
          id?: string
          role_id?: string
          section_type?: string
          can_edit?: boolean
        }
        Relationships: []
      }
      plan_fact_products: {
        Row: {
          id: string
          quote_id: string
          accepted_version_id: string
          product_id: string
          organization_id: string
          section_type: string
          plan_amount_quote_currency: number
          plan_amount_org_currency: number
          fact_amount: number | null
          fact_currency: string | null
          fact_date: string | null
          fact_amount_quote_currency: number | null
          fact_amount_org_currency: number | null
          exchange_rate_fact_to_quote: number | null
          exchange_rate_fact_to_org: number | null
          exchange_rate_date: string | null
          entered_by: string | null
          entered_at: string | null
          updated_by: string | null
          updated_at: string | null
          notes: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          accepted_version_id: string
          product_id: string
          organization_id: string
          section_type: string
          plan_amount_quote_currency: number
          plan_amount_org_currency: number
          fact_amount?: number | null
          fact_currency?: string | null
          fact_date?: string | null
          fact_amount_quote_currency?: number | null
          fact_amount_org_currency?: number | null
          exchange_rate_fact_to_quote?: number | null
          exchange_rate_fact_to_org?: number | null
          exchange_rate_date?: string | null
          entered_by?: string | null
          entered_at?: string | null
          updated_by?: string | null
          updated_at?: string | null
          notes?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          accepted_version_id?: string
          product_id?: string
          organization_id?: string
          section_type?: string
          plan_amount_quote_currency?: number
          plan_amount_org_currency?: number
          fact_amount?: number | null
          fact_currency?: string | null
          fact_date?: string | null
          fact_amount_quote_currency?: number | null
          fact_amount_org_currency?: number | null
          exchange_rate_fact_to_quote?: number | null
          exchange_rate_fact_to_org?: number | null
          exchange_rate_date?: string | null
          entered_by?: string | null
          entered_at?: string | null
          updated_by?: string | null
          updated_at?: string | null
          notes?: string | null
        }
        Relationships: []
      }
      plan_fact_sections: {
        Row: {
          id: string
          quote_id: string
          accepted_version_id: string
          section_type: string
          organization_id: string
          plan_amount_quote_currency: number
          plan_amount_org_currency: number
          fact_amount: number | null
          fact_currency: string | null
          fact_date: string | null
          fact_amount_quote_currency: number | null
          fact_amount_org_currency: number | null
          exchange_rate_fact_to_quote: number | null
          exchange_rate_fact_to_org: number | null
          exchange_rate_date: string | null
          entered_by: string | null
          entered_at: string | null
          updated_by: string | null
          updated_at: string | null
          notes: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          accepted_version_id: string
          section_type: string
          organization_id: string
          plan_amount_quote_currency: number
          plan_amount_org_currency: number
          fact_amount?: number | null
          fact_currency?: string | null
          fact_date?: string | null
          fact_amount_quote_currency?: number | null
          fact_amount_org_currency?: number | null
          exchange_rate_fact_to_quote?: number | null
          exchange_rate_fact_to_org?: number | null
          exchange_rate_date?: string | null
          entered_by?: string | null
          entered_at?: string | null
          updated_by?: string | null
          updated_at?: string | null
          notes?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          accepted_version_id?: string
          section_type?: string
          organization_id?: string
          plan_amount_quote_currency?: number
          plan_amount_org_currency?: number
          fact_amount?: number | null
          fact_currency?: string | null
          fact_date?: string | null
          fact_amount_quote_currency?: number | null
          fact_amount_org_currency?: number | null
          exchange_rate_fact_to_quote?: number | null
          exchange_rate_fact_to_org?: number | null
          exchange_rate_date?: string | null
          entered_by?: string | null
          entered_at?: string | null
          updated_by?: string | null
          updated_at?: string | null
          notes?: string | null
        }
        Relationships: []
      }
      purchasing_companies: {
        Row: {
          id: string
          organization_id: string
          name: string
          country: string
          is_active: boolean | null
          created_at: string | null
          updated_at: string | null
          short_name: string | null
          currency: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          name: string
          country: string
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          short_name?: string | null
          currency?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          name?: string
          country?: string
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          short_name?: string | null
          currency?: string | null
        }
        Relationships: []
      }
      quote_approval_history: {
        Row: {
          id: string
          quote_id: string
          organization_id: string
          approver_user_id: string
          workflow_state: string
          approved_at: string | null
          comment: string | null
          created_at: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          organization_id: string
          approver_user_id: string
          workflow_state: string
          approved_at?: string | null
          comment?: string | null
          created_at?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          organization_id?: string
          approver_user_id?: string
          workflow_state?: string
          approved_at?: string | null
          comment?: string | null
          created_at?: string | null
        }
        Relationships: []
      }
      quote_calculation_products_versioned: {
        Row: {
          id: string
          quote_version_id: string
          product_id: string
          purchase_price_total: number | null
          logistics_allocated: number | null
          duties_total: number | null
          brokerage_allocated: number | null
          financing_allocated: number | null
          cost_of_goods_sold: number | null
          sale_price_per_unit: number | null
          sale_price_total: number | null
          profit_per_product: number | null
          margin_percent: number | null
          purchase_price_total_org_currency: number | null
          cost_of_goods_sold_org_currency: number | null
          sale_price_total_org_currency: number | null
          profit_per_product_org_currency: number | null
          organization_id: string | null
        }
        Insert: {
          id?: string
          quote_version_id: string
          product_id: string
          purchase_price_total?: number | null
          logistics_allocated?: number | null
          duties_total?: number | null
          brokerage_allocated?: number | null
          financing_allocated?: number | null
          cost_of_goods_sold?: number | null
          sale_price_per_unit?: number | null
          sale_price_total?: number | null
          profit_per_product?: number | null
          margin_percent?: number | null
          purchase_price_total_org_currency?: number | null
          cost_of_goods_sold_org_currency?: number | null
          sale_price_total_org_currency?: number | null
          profit_per_product_org_currency?: number | null
          organization_id?: string | null
        }
        Update: {
          id?: string
          quote_version_id?: string
          product_id?: string
          purchase_price_total?: number | null
          logistics_allocated?: number | null
          duties_total?: number | null
          brokerage_allocated?: number | null
          financing_allocated?: number | null
          cost_of_goods_sold?: number | null
          sale_price_per_unit?: number | null
          sale_price_total?: number | null
          profit_per_product?: number | null
          margin_percent?: number | null
          purchase_price_total_org_currency?: number | null
          cost_of_goods_sold_org_currency?: number | null
          sale_price_total_org_currency?: number | null
          profit_per_product_org_currency?: number | null
          organization_id?: string | null
        }
        Relationships: []
      }
      quote_calculation_results: {
        Row: {
          id: string
          quote_id: string
          quote_item_id: string
          phase_results: Json
          calculated_at: string | null
          phase_results_quote_currency: Json | null
          phase_results_usd: Json | null
        }
        Insert: {
          id?: string
          quote_id: string
          quote_item_id: string
          phase_results: Json
          calculated_at?: string | null
          phase_results_quote_currency?: Json | null
          phase_results_usd?: Json | null
        }
        Update: {
          id?: string
          quote_id?: string
          quote_item_id?: string
          phase_results?: Json
          calculated_at?: string | null
          phase_results_quote_currency?: Json | null
          phase_results_usd?: Json | null
        }
        Relationships: []
      }
      quote_calculation_summaries: {
        Row: {
          quote_id: string
          calc_n16_price_without_vat: number | null
          calc_p16_after_supplier_discount: number | null
          calc_r16_per_unit_quote_currency: number | null
          calc_s16_total_purchase_price: number | null
          calc_s13_sum_purchase_prices: number | null
          calc_t16_first_leg_logistics: number | null
          calc_u16_last_leg_logistics: number | null
          calc_v16_total_logistics: number | null
          calc_ax16_internal_price_unit: number | null
          calc_ay16_internal_price_total: number | null
          calc_y16_customs_duty: number | null
          calc_z16_excise_tax: number | null
          calc_az16_with_vat_restored: number | null
          calc_bh6_supplier_payment: number | null
          calc_bh4_before_forwarding: number | null
          calc_bh2_revenue_estimated: number | null
          calc_bh3_client_advance: number | null
          calc_bh7_supplier_financing_need: number | null
          calc_bj7_supplier_financing_cost: number | null
          calc_bh10_operational_financing: number | null
          calc_bj10_operational_cost: number | null
          calc_bj11_total_financing_cost: number | null
          calc_bl3_credit_sales_amount: number | null
          calc_bl4_credit_sales_with_interest: number | null
          calc_bl5_credit_sales_interest: number | null
          calc_ba16_financing_per_product: number | null
          calc_bb16_credit_interest_per_product: number | null
          calc_aa16_cogs_per_unit: number | null
          calc_ab16_cogs_total: number | null
          calc_af16_profit_margin: number | null
          calc_ag16_dm_fee: number | null
          calc_ah16_forex_risk_reserve: number | null
          calc_ai16_agent_fee: number | null
          calc_ad16_sale_price_unit: number | null
          calc_ae16_sale_price_total: number | null
          calc_aj16_final_price_unit: number | null
          calc_ak16_final_price_total: number | null
          calc_am16_price_with_vat: number | null
          calc_al16_total_with_vat: number | null
          calc_an16_sales_vat: number | null
          calc_ao16_deductible_vat: number | null
          calc_ap16_net_vat_payable: number | null
          calc_aq16_transit_commission: number | null
          calculated_at: string | null
          updated_at: string | null
          calc_total_brokerage: number | null
          calc_total_logistics_and_brokerage: number | null
          quote_currency: string | null
          usd_to_quote_rate: number | null
          exchange_rate_source: string | null
          exchange_rate_timestamp: string | null
          calc_s16_total_purchase_price_quote: number | null
          calc_v16_total_logistics_quote: number | null
          calc_ab16_cogs_total_quote: number | null
          calc_ak16_final_price_total_quote: number | null
          calc_al16_total_with_vat_quote: number | null
          calc_total_brokerage_quote: number | null
          calc_total_logistics_and_brokerage_quote: number | null
          exchange_rate_to_usd: number | null
          calc_s16_total_purchase_price_usd: number | null
          calc_v16_total_logistics_usd: number | null
          calc_y16_customs_duty_usd: number | null
          calc_total_brokerage_usd: number | null
          calc_ae16_sale_price_total_usd: number | null
          calc_al16_total_with_vat_usd: number | null
          calc_af16_total_profit_usd: number | null
        }
        Insert: {
          quote_id: string
          calc_n16_price_without_vat?: number | null
          calc_p16_after_supplier_discount?: number | null
          calc_r16_per_unit_quote_currency?: number | null
          calc_s16_total_purchase_price?: number | null
          calc_s13_sum_purchase_prices?: number | null
          calc_t16_first_leg_logistics?: number | null
          calc_u16_last_leg_logistics?: number | null
          calc_v16_total_logistics?: number | null
          calc_ax16_internal_price_unit?: number | null
          calc_ay16_internal_price_total?: number | null
          calc_y16_customs_duty?: number | null
          calc_z16_excise_tax?: number | null
          calc_az16_with_vat_restored?: number | null
          calc_bh6_supplier_payment?: number | null
          calc_bh4_before_forwarding?: number | null
          calc_bh2_revenue_estimated?: number | null
          calc_bh3_client_advance?: number | null
          calc_bh7_supplier_financing_need?: number | null
          calc_bj7_supplier_financing_cost?: number | null
          calc_bh10_operational_financing?: number | null
          calc_bj10_operational_cost?: number | null
          calc_bj11_total_financing_cost?: number | null
          calc_bl3_credit_sales_amount?: number | null
          calc_bl4_credit_sales_with_interest?: number | null
          calc_bl5_credit_sales_interest?: number | null
          calc_ba16_financing_per_product?: number | null
          calc_bb16_credit_interest_per_product?: number | null
          calc_aa16_cogs_per_unit?: number | null
          calc_ab16_cogs_total?: number | null
          calc_af16_profit_margin?: number | null
          calc_ag16_dm_fee?: number | null
          calc_ah16_forex_risk_reserve?: number | null
          calc_ai16_agent_fee?: number | null
          calc_ad16_sale_price_unit?: number | null
          calc_ae16_sale_price_total?: number | null
          calc_aj16_final_price_unit?: number | null
          calc_ak16_final_price_total?: number | null
          calc_am16_price_with_vat?: number | null
          calc_al16_total_with_vat?: number | null
          calc_an16_sales_vat?: number | null
          calc_ao16_deductible_vat?: number | null
          calc_ap16_net_vat_payable?: number | null
          calc_aq16_transit_commission?: number | null
          calculated_at?: string | null
          updated_at?: string | null
          calc_total_brokerage?: number | null
          calc_total_logistics_and_brokerage?: number | null
          quote_currency?: string | null
          usd_to_quote_rate?: number | null
          exchange_rate_source?: string | null
          exchange_rate_timestamp?: string | null
          calc_s16_total_purchase_price_quote?: number | null
          calc_v16_total_logistics_quote?: number | null
          calc_ab16_cogs_total_quote?: number | null
          calc_ak16_final_price_total_quote?: number | null
          calc_al16_total_with_vat_quote?: number | null
          calc_total_brokerage_quote?: number | null
          calc_total_logistics_and_brokerage_quote?: number | null
          exchange_rate_to_usd?: number | null
          calc_s16_total_purchase_price_usd?: number | null
          calc_v16_total_logistics_usd?: number | null
          calc_y16_customs_duty_usd?: number | null
          calc_total_brokerage_usd?: number | null
          calc_ae16_sale_price_total_usd?: number | null
          calc_al16_total_with_vat_usd?: number | null
          calc_af16_total_profit_usd?: number | null
        }
        Update: {
          quote_id?: string
          calc_n16_price_without_vat?: number | null
          calc_p16_after_supplier_discount?: number | null
          calc_r16_per_unit_quote_currency?: number | null
          calc_s16_total_purchase_price?: number | null
          calc_s13_sum_purchase_prices?: number | null
          calc_t16_first_leg_logistics?: number | null
          calc_u16_last_leg_logistics?: number | null
          calc_v16_total_logistics?: number | null
          calc_ax16_internal_price_unit?: number | null
          calc_ay16_internal_price_total?: number | null
          calc_y16_customs_duty?: number | null
          calc_z16_excise_tax?: number | null
          calc_az16_with_vat_restored?: number | null
          calc_bh6_supplier_payment?: number | null
          calc_bh4_before_forwarding?: number | null
          calc_bh2_revenue_estimated?: number | null
          calc_bh3_client_advance?: number | null
          calc_bh7_supplier_financing_need?: number | null
          calc_bj7_supplier_financing_cost?: number | null
          calc_bh10_operational_financing?: number | null
          calc_bj10_operational_cost?: number | null
          calc_bj11_total_financing_cost?: number | null
          calc_bl3_credit_sales_amount?: number | null
          calc_bl4_credit_sales_with_interest?: number | null
          calc_bl5_credit_sales_interest?: number | null
          calc_ba16_financing_per_product?: number | null
          calc_bb16_credit_interest_per_product?: number | null
          calc_aa16_cogs_per_unit?: number | null
          calc_ab16_cogs_total?: number | null
          calc_af16_profit_margin?: number | null
          calc_ag16_dm_fee?: number | null
          calc_ah16_forex_risk_reserve?: number | null
          calc_ai16_agent_fee?: number | null
          calc_ad16_sale_price_unit?: number | null
          calc_ae16_sale_price_total?: number | null
          calc_aj16_final_price_unit?: number | null
          calc_ak16_final_price_total?: number | null
          calc_am16_price_with_vat?: number | null
          calc_al16_total_with_vat?: number | null
          calc_an16_sales_vat?: number | null
          calc_ao16_deductible_vat?: number | null
          calc_ap16_net_vat_payable?: number | null
          calc_aq16_transit_commission?: number | null
          calculated_at?: string | null
          updated_at?: string | null
          calc_total_brokerage?: number | null
          calc_total_logistics_and_brokerage?: number | null
          quote_currency?: string | null
          usd_to_quote_rate?: number | null
          exchange_rate_source?: string | null
          exchange_rate_timestamp?: string | null
          calc_s16_total_purchase_price_quote?: number | null
          calc_v16_total_logistics_quote?: number | null
          calc_ab16_cogs_total_quote?: number | null
          calc_ak16_final_price_total_quote?: number | null
          calc_al16_total_with_vat_quote?: number | null
          calc_total_brokerage_quote?: number | null
          calc_total_logistics_and_brokerage_quote?: number | null
          exchange_rate_to_usd?: number | null
          calc_s16_total_purchase_price_usd?: number | null
          calc_v16_total_logistics_usd?: number | null
          calc_y16_customs_duty_usd?: number | null
          calc_total_brokerage_usd?: number | null
          calc_ae16_sale_price_total_usd?: number | null
          calc_al16_total_with_vat_usd?: number | null
          calc_af16_total_profit_usd?: number | null
        }
        Relationships: []
      }
      quote_calculation_summaries_versioned: {
        Row: {
          id: string
          quote_version_id: string
          total_purchase_price_quote_currency: number | null
          total_logistics_quote_currency: number | null
          total_duties_quote_currency: number | null
          total_brokerage_quote_currency: number | null
          total_financing_quote_currency: number | null
          total_cost_quote_currency: number | null
          total_purchase_price_org_currency: number | null
          total_logistics_org_currency: number | null
          total_duties_org_currency: number | null
          total_brokerage_org_currency: number | null
          total_financing_org_currency: number | null
          total_cost_org_currency: number | null
          total_revenue_quote_currency: number | null
          profit_quote_currency: number | null
          total_revenue_org_currency: number | null
          profit_org_currency: number | null
          margin_percent: number | null
          currency_quote: string
          currency_org: string
          exchange_rate_quote_to_org: number
          calculated_at: string | null
          organization_id: string | null
        }
        Insert: {
          id?: string
          quote_version_id: string
          total_purchase_price_quote_currency?: number | null
          total_logistics_quote_currency?: number | null
          total_duties_quote_currency?: number | null
          total_brokerage_quote_currency?: number | null
          total_financing_quote_currency?: number | null
          total_cost_quote_currency?: number | null
          total_purchase_price_org_currency?: number | null
          total_logistics_org_currency?: number | null
          total_duties_org_currency?: number | null
          total_brokerage_org_currency?: number | null
          total_financing_org_currency?: number | null
          total_cost_org_currency?: number | null
          total_revenue_quote_currency?: number | null
          profit_quote_currency?: number | null
          total_revenue_org_currency?: number | null
          profit_org_currency?: number | null
          margin_percent?: number | null
          currency_quote: string
          currency_org: string
          exchange_rate_quote_to_org: number
          calculated_at?: string | null
          organization_id?: string | null
        }
        Update: {
          id?: string
          quote_version_id?: string
          total_purchase_price_quote_currency?: number | null
          total_logistics_quote_currency?: number | null
          total_duties_quote_currency?: number | null
          total_brokerage_quote_currency?: number | null
          total_financing_quote_currency?: number | null
          total_cost_quote_currency?: number | null
          total_purchase_price_org_currency?: number | null
          total_logistics_org_currency?: number | null
          total_duties_org_currency?: number | null
          total_brokerage_org_currency?: number | null
          total_financing_org_currency?: number | null
          total_cost_org_currency?: number | null
          total_revenue_quote_currency?: number | null
          profit_quote_currency?: number | null
          total_revenue_org_currency?: number | null
          profit_org_currency?: number | null
          margin_percent?: number | null
          currency_quote?: string
          currency_org?: string
          exchange_rate_quote_to_org?: number
          calculated_at?: string | null
          organization_id?: string | null
        }
        Relationships: []
      }
      quote_calculation_variables: {
        Row: {
          id: string
          quote_id: string
          template_id: string | null
          variables: Json
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          template_id?: string | null
          variables: Json
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          template_id?: string | null
          variables?: Json
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      quote_change_requests: {
        Row: {
          id: string
          quote_id: string
          change_type: string
          client_comment: string | null
          requested_by: string | null
          requested_at: string | null
          resolved_at: string | null
          resolution_notes: string | null
          created_at: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          change_type: string
          client_comment?: string | null
          requested_by?: string | null
          requested_at?: string | null
          resolved_at?: string | null
          resolution_notes?: string | null
          created_at?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          change_type?: string
          client_comment?: string | null
          requested_by?: string | null
          requested_at?: string | null
          resolved_at?: string | null
          resolution_notes?: string | null
          created_at?: string | null
        }
        Relationships: []
      }
      quote_comment_reads: {
        Row: {
          quote_id: string
          user_id: string
          last_read_at: string
        }
        Insert: {
          quote_id: string
          user_id: string
          last_read_at?: string
        }
        Update: {
          quote_id?: string
          user_id?: string
          last_read_at?: string
        }
        Relationships: []
      }
      quote_comments: {
        Row: {
          id: string
          quote_id: string
          user_id: string
          body: string
          mentions: Json
          created_at: string
        }
        Insert: {
          id?: string
          quote_id: string
          user_id: string
          body: string
          mentions?: Json
          created_at?: string
        }
        Update: {
          id?: string
          quote_id?: string
          user_id?: string
          body?: string
          mentions?: Json
          created_at?: string
        }
        Relationships: []
      }
      quote_export_settings: {
        Row: {
          id: string
          organization_id: string
          user_id: string | null
          customer_id: string | null
          setting_type: string
          visible_columns: Json
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          user_id?: string | null
          customer_id?: string | null
          setting_type: string
          visible_columns: Json
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          user_id?: string | null
          customer_id?: string | null
          setting_type?: string
          visible_columns?: Json
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      quote_items: {
        Row: {
          id: string
          quote_id: string
          position: number
          product_name: string
          product_code: string | null
          base_price_vat: number | null
          quantity: number
          weight_in_kg: number | null
          customs_code: string | null
          supplier_country: string | null
          description: string | null
          unit: string | null
          created_at: string | null
          updated_at: string | null
          brand: string | null
          custom_fields: Json | null
          idn_sku: string | null
          production_time_days: number | null
          product_category: string | null
          proforma_number: string | null
          proforma_date: string | null
          proforma_currency: string | null
          proforma_amount_excl_vat: number | null
          proforma_amount_incl_vat: number | null
          proforma_amount_excl_vat_usd: number | null
          proforma_amount_incl_vat_usd: number | null
          purchasing_company_id: string | null
          supplier_id: string | null
          purchasing_manager_id: string | null
          pickup_country: string | null
          supplier_payment_country: string | null
          procurement_status: string | null
          procurement_completed_at: string | null
          procurement_completed_by: string | null
          hs_code: string | null
          customs_duty: number | null
          customs_extra: number | null
          supplier_payment_terms: string | null
          payer_company: string | null
          advance_to_supplier_percent: number | null
          procurement_notes: string | null
          assigned_procurement_user: string | null
          supplier_city: string | null
          logistics_supplier_to_hub: number | null
          logistics_hub_to_customs: number | null
          logistics_customs_to_customer: number | null
          logistics_total_days: number | null
          purchase_currency: string | null
          invoice_id: string | null
          buyer_company_id: string | null
          pickup_location_id: string | null
          purchase_price_original: number | null
          volume_m3: number | null
          is_unavailable: boolean | null
          price_includes_vat: boolean | null
          license_ds_required: boolean | null
          license_ds_cost: number | null
          license_ss_required: boolean | null
          license_ss_cost: number | null
          license_sgr_required: boolean | null
          license_sgr_cost: number | null
          supplier_sku: string | null
          item_idn: string | null
          supplier_advance_percent: number | null
          weight_kg: number | null
          customs_duty_percent: number | null
          customs_extra_cost: number | null
          supplier_sku_note: string | null
          manufacturer_product_name: string | null
          dimension_height_mm: number | null
          dimension_width_mm: number | null
          dimension_length_mm: number | null
          vat_rate: number | null
          customs_ds_sgr: string | null
          customs_util_fee: number | null
          customs_excise: number | null
          customs_psn_pts: string | null
          customs_notification: string | null
          customs_licenses: string | null
          customs_marking: string | null
          customs_eco_fee: number | null
          customs_honest_mark: string | null
          customs_duty_per_kg: number | null
          import_banned: boolean | null
          import_ban_reason: string | null
          composition_selected_invoice_id: string | null
          min_order_quantity: number | null
          name_en: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          position?: number
          product_name: string
          product_code?: string | null
          base_price_vat?: number | null
          quantity: number
          weight_in_kg?: number | null
          customs_code?: string | null
          supplier_country?: string | null
          description?: string | null
          unit?: string | null
          created_at?: string | null
          updated_at?: string | null
          brand?: string | null
          custom_fields?: Json | null
          idn_sku?: string | null
          production_time_days?: number | null
          product_category?: string | null
          proforma_number?: string | null
          proforma_date?: string | null
          proforma_currency?: string | null
          proforma_amount_excl_vat?: number | null
          proforma_amount_incl_vat?: number | null
          proforma_amount_excl_vat_usd?: number | null
          proforma_amount_incl_vat_usd?: number | null
          purchasing_company_id?: string | null
          supplier_id?: string | null
          purchasing_manager_id?: string | null
          pickup_country?: string | null
          supplier_payment_country?: string | null
          procurement_status?: string | null
          procurement_completed_at?: string | null
          procurement_completed_by?: string | null
          hs_code?: string | null
          customs_duty?: number | null
          customs_extra?: number | null
          supplier_payment_terms?: string | null
          payer_company?: string | null
          advance_to_supplier_percent?: number | null
          procurement_notes?: string | null
          assigned_procurement_user?: string | null
          supplier_city?: string | null
          logistics_supplier_to_hub?: number | null
          logistics_hub_to_customs?: number | null
          logistics_customs_to_customer?: number | null
          logistics_total_days?: number | null
          purchase_currency?: string | null
          invoice_id?: string | null
          buyer_company_id?: string | null
          pickup_location_id?: string | null
          purchase_price_original?: number | null
          volume_m3?: number | null
          is_unavailable?: boolean | null
          price_includes_vat?: boolean | null
          license_ds_required?: boolean | null
          license_ds_cost?: number | null
          license_ss_required?: boolean | null
          license_ss_cost?: number | null
          license_sgr_required?: boolean | null
          license_sgr_cost?: number | null
          supplier_sku?: string | null
          item_idn?: string | null
          supplier_advance_percent?: number | null
          weight_kg?: number | null
          customs_duty_percent?: number | null
          customs_extra_cost?: number | null
          supplier_sku_note?: string | null
          manufacturer_product_name?: string | null
          dimension_height_mm?: number | null
          dimension_width_mm?: number | null
          dimension_length_mm?: number | null
          vat_rate?: number | null
          customs_ds_sgr?: string | null
          customs_util_fee?: number | null
          customs_excise?: number | null
          customs_psn_pts?: string | null
          customs_notification?: string | null
          customs_licenses?: string | null
          customs_marking?: string | null
          customs_eco_fee?: number | null
          customs_honest_mark?: string | null
          customs_duty_per_kg?: number | null
          import_banned?: boolean | null
          import_ban_reason?: string | null
          composition_selected_invoice_id?: string | null
          min_order_quantity?: number | null
          name_en?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          position?: number
          product_name?: string
          product_code?: string | null
          base_price_vat?: number | null
          quantity?: number
          weight_in_kg?: number | null
          customs_code?: string | null
          supplier_country?: string | null
          description?: string | null
          unit?: string | null
          created_at?: string | null
          updated_at?: string | null
          brand?: string | null
          custom_fields?: Json | null
          idn_sku?: string | null
          production_time_days?: number | null
          product_category?: string | null
          proforma_number?: string | null
          proforma_date?: string | null
          proforma_currency?: string | null
          proforma_amount_excl_vat?: number | null
          proforma_amount_incl_vat?: number | null
          proforma_amount_excl_vat_usd?: number | null
          proforma_amount_incl_vat_usd?: number | null
          purchasing_company_id?: string | null
          supplier_id?: string | null
          purchasing_manager_id?: string | null
          pickup_country?: string | null
          supplier_payment_country?: string | null
          procurement_status?: string | null
          procurement_completed_at?: string | null
          procurement_completed_by?: string | null
          hs_code?: string | null
          customs_duty?: number | null
          customs_extra?: number | null
          supplier_payment_terms?: string | null
          payer_company?: string | null
          advance_to_supplier_percent?: number | null
          procurement_notes?: string | null
          assigned_procurement_user?: string | null
          supplier_city?: string | null
          logistics_supplier_to_hub?: number | null
          logistics_hub_to_customs?: number | null
          logistics_customs_to_customer?: number | null
          logistics_total_days?: number | null
          purchase_currency?: string | null
          invoice_id?: string | null
          buyer_company_id?: string | null
          pickup_location_id?: string | null
          purchase_price_original?: number | null
          volume_m3?: number | null
          is_unavailable?: boolean | null
          price_includes_vat?: boolean | null
          license_ds_required?: boolean | null
          license_ds_cost?: number | null
          license_ss_required?: boolean | null
          license_ss_cost?: number | null
          license_sgr_required?: boolean | null
          license_sgr_cost?: number | null
          supplier_sku?: string | null
          item_idn?: string | null
          supplier_advance_percent?: number | null
          weight_kg?: number | null
          customs_duty_percent?: number | null
          customs_extra_cost?: number | null
          supplier_sku_note?: string | null
          manufacturer_product_name?: string | null
          dimension_height_mm?: number | null
          dimension_width_mm?: number | null
          dimension_length_mm?: number | null
          vat_rate?: number | null
          customs_ds_sgr?: string | null
          customs_util_fee?: number | null
          customs_excise?: number | null
          customs_psn_pts?: string | null
          customs_notification?: string | null
          customs_licenses?: string | null
          customs_marking?: string | null
          customs_eco_fee?: number | null
          customs_honest_mark?: string | null
          customs_duty_per_kg?: number | null
          import_banned?: boolean | null
          import_ban_reason?: string | null
          composition_selected_invoice_id?: string | null
          min_order_quantity?: number | null
          name_en?: string | null
        }
        Relationships: []
      }
      quote_timeline_events: {
        Row: {
          id: string
          quote_id: string
          event_type: string
          organization_id: string
          plan_date: string | null
          plan_days_from_signing: number | null
          fact_date: string | null
          fact_days_from_signing: number | null
          delay_days: number | null
          entered_by: string | null
          entered_at: string | null
          notes: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          event_type: string
          organization_id: string
          plan_date?: string | null
          plan_days_from_signing?: number | null
          fact_date?: string | null
          fact_days_from_signing?: number | null
          delay_days?: number | null
          entered_by?: string | null
          entered_at?: string | null
          notes?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          event_type?: string
          organization_id?: string
          plan_date?: string | null
          plan_days_from_signing?: number | null
          fact_date?: string | null
          fact_days_from_signing?: number | null
          delay_days?: number | null
          entered_by?: string | null
          entered_at?: string | null
          notes?: string | null
        }
        Relationships: []
      }
      quote_versions: {
        Row: {
          id: string
          quote_id: string
          version: number
          status: string
          customer_id: string
          title: string | null
          description: string | null
          quote_date: string | null
          valid_until: string | null
          notes: string | null
          terms_conditions: string | null
          seller_company: string | null
          offer_sale_type: string | null
          offer_incoterms: string | null
          currency_of_quote: string | null
          created_at: string | null
          created_by: string
          input_variables: Json | null
        }
        Insert: {
          id?: string
          quote_id: string
          version: number
          status: string
          customer_id: string
          title?: string | null
          description?: string | null
          quote_date?: string | null
          valid_until?: string | null
          notes?: string | null
          terms_conditions?: string | null
          seller_company?: string | null
          offer_sale_type?: string | null
          offer_incoterms?: string | null
          currency_of_quote?: string | null
          created_at?: string | null
          created_by: string
          input_variables?: Json | null
        }
        Update: {
          id?: string
          quote_id?: string
          version?: number
          status?: string
          customer_id?: string
          title?: string | null
          description?: string | null
          quote_date?: string | null
          valid_until?: string | null
          notes?: string | null
          terms_conditions?: string | null
          seller_company?: string | null
          offer_sale_type?: string | null
          offer_incoterms?: string | null
          currency_of_quote?: string | null
          created_at?: string | null
          created_by?: string
          input_variables?: Json | null
        }
        Relationships: []
      }
      quote_workflow_transitions: {
        Row: {
          id: string
          quote_id: string
          organization_id: string
          from_state: string
          to_state: string
          action: string
          performed_by: string
          performed_at: string | null
          role_at_transition: string
          comments: string | null
          reason: string | null
          created_at: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          organization_id: string
          from_state: string
          to_state: string
          action: string
          performed_by: string
          performed_at?: string | null
          role_at_transition: string
          comments?: string | null
          reason?: string | null
          created_at?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          organization_id?: string
          from_state?: string
          to_state?: string
          action?: string
          performed_by?: string
          performed_at?: string | null
          role_at_transition?: string
          comments?: string | null
          reason?: string | null
          created_at?: string | null
        }
        Relationships: []
      }
      quotes: {
        Row: {
          id: string
          organization_id: string
          customer_id: string | null
          idn_quote: string
          title: string
          description: string | null
          status: string
          valid_until: string | null
          subtotal: number
          tax_rate: number | null
          tax_amount: number | null
          total_amount: number
          notes: string | null
          terms_conditions: string | null
          created_by: string
          created_at: string | null
          updated_at: string | null
          quote_date: string
          deleted_at: string | null
          delivery_address: string | null
          contact_id: string | null
          created_by_user_id: string | null
          manager_name: string | null
          manager_phone: string | null
          manager_email: string | null
          workflow_state: string
          logistics_complete: boolean | null
          customs_complete: boolean | null
          current_assignee_role: string | null
          assigned_at: string | null
          senior_approvals_required: number | null
          senior_approvals_received: number | null
          current_version: number | null
          accepted_version_id: string | null
          last_financial_comment: string | null
          last_sendback_reason: string | null
          financial_reviewed_at: string | null
          financial_reviewed_by: string | null
          submission_comment: string | null
          last_approval_comment: string | null
          current_version_id: string | null
          total_usd: number | null
          total_quote_currency: number | null
          last_calculated_at: string | null
          version_count: number
          currency: string
          total_profit_usd: number | null
          total_vat_on_import_usd: number | null
          total_vat_payable_usd: number | null
          usd_to_quote_rate: number | null
          exchange_rate_source: string | null
          exchange_rate_timestamp: string | null
          total_amount_quote: number | null
          total_with_vat_quote: number | null
          total_with_vat_usd: number | null
          payment_terms: string | null
          delivery_days: number | null
          delivery_terms: string | null
          document_folder_link: string | null
          executor_user_id: string | null
          spec_sign_date: string | null
          total_quantity: number | null
          total_weight_kg: number | null
          delivery_city: string | null
          cargo_type: string | null
          deal_type: string | null
          assigned_procurement_users: Json | null
          assigned_logistics_user: string | null
          assigned_customs_user: string | null
          procurement_completed_at: string | null
          logistics_completed_at: string | null
          customs_completed_at: string | null
          workflow_status: string | null
          approvals: Json | null
          seller_company_id: string | null
          delivery_country: string | null
          delivery_method: string | null
          revision_department: string | null
          revision_comment: string | null
          revision_returned_at: string | null
          approval_reason: string | null
          approval_justification: string | null
          needs_justification: boolean | null
          exchange_rate_to_usd: number | null
          subtotal_usd: number | null
          total_amount_usd: number | null
          sent_at: string | null
          sent_to_email: string | null
          partial_recalc: string | null
          rejection_reason: string | null
          rejection_comment: string | null
          rejected_at: string | null
          rejected_by: string | null
          validity_days: number | null
          delivery_priority: string | null
          contact_person_id: string | null
          sales_checklist: Json | null
          profit_quote_currency: number | null
          quote_controller_id: string | null
          quote_control_completed_at: string | null
          spec_controller_id: string | null
          spec_control_completed_at: string | null
          additional_info: string | null
          is_phmb: boolean
          phmb_advance_pct: number | null
          phmb_markup_pct: number | null
          phmb_payment_days: number | null
          cogs_quote_currency: number | null
          revenue_no_vat_quote_currency: number | null
          idn: string | null
          tender_type: string | null
          competitors: string | null
          cancellation_reason: string | null
          cancellation_comment: string | null
          stage_entered_at: string | null
          stage_deadline_override_hours: number | null
          overdue_notified_at: string | null
          cancelled_at: string | null
          cancelled_by: string | null
          incoterms: string | null
          procurement_substatus: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          customer_id?: string | null
          idn_quote: string
          title: string
          description?: string | null
          status?: string
          valid_until?: string | null
          subtotal?: number
          tax_rate?: number | null
          tax_amount?: number | null
          total_amount?: number
          notes?: string | null
          terms_conditions?: string | null
          created_by: string
          created_at?: string | null
          updated_at?: string | null
          quote_date?: string
          deleted_at?: string | null
          delivery_address?: string | null
          contact_id?: string | null
          created_by_user_id?: string | null
          manager_name?: string | null
          manager_phone?: string | null
          manager_email?: string | null
          workflow_state?: string
          logistics_complete?: boolean | null
          customs_complete?: boolean | null
          current_assignee_role?: string | null
          assigned_at?: string | null
          senior_approvals_required?: number | null
          senior_approvals_received?: number | null
          current_version?: number | null
          accepted_version_id?: string | null
          last_financial_comment?: string | null
          last_sendback_reason?: string | null
          financial_reviewed_at?: string | null
          financial_reviewed_by?: string | null
          submission_comment?: string | null
          last_approval_comment?: string | null
          current_version_id?: string | null
          total_usd?: number | null
          total_quote_currency?: number | null
          last_calculated_at?: string | null
          version_count?: number
          currency?: string
          total_profit_usd?: number | null
          total_vat_on_import_usd?: number | null
          total_vat_payable_usd?: number | null
          usd_to_quote_rate?: number | null
          exchange_rate_source?: string | null
          exchange_rate_timestamp?: string | null
          total_amount_quote?: number | null
          total_with_vat_quote?: number | null
          total_with_vat_usd?: number | null
          payment_terms?: string | null
          delivery_days?: number | null
          delivery_terms?: string | null
          document_folder_link?: string | null
          executor_user_id?: string | null
          spec_sign_date?: string | null
          total_quantity?: number | null
          total_weight_kg?: number | null
          delivery_city?: string | null
          cargo_type?: string | null
          deal_type?: string | null
          assigned_procurement_users?: Json | null
          assigned_logistics_user?: string | null
          assigned_customs_user?: string | null
          procurement_completed_at?: string | null
          logistics_completed_at?: string | null
          customs_completed_at?: string | null
          workflow_status?: string | null
          approvals?: Json | null
          seller_company_id?: string | null
          delivery_country?: string | null
          delivery_method?: string | null
          revision_department?: string | null
          revision_comment?: string | null
          revision_returned_at?: string | null
          approval_reason?: string | null
          approval_justification?: string | null
          needs_justification?: boolean | null
          exchange_rate_to_usd?: number | null
          subtotal_usd?: number | null
          total_amount_usd?: number | null
          sent_at?: string | null
          sent_to_email?: string | null
          partial_recalc?: string | null
          rejection_reason?: string | null
          rejection_comment?: string | null
          rejected_at?: string | null
          rejected_by?: string | null
          validity_days?: number | null
          delivery_priority?: string | null
          contact_person_id?: string | null
          sales_checklist?: Json | null
          profit_quote_currency?: number | null
          quote_controller_id?: string | null
          quote_control_completed_at?: string | null
          spec_controller_id?: string | null
          spec_control_completed_at?: string | null
          additional_info?: string | null
          is_phmb?: boolean
          phmb_advance_pct?: number | null
          phmb_markup_pct?: number | null
          phmb_payment_days?: number | null
          cogs_quote_currency?: number | null
          revenue_no_vat_quote_currency?: number | null
          idn?: string | null
          tender_type?: string | null
          competitors?: string | null
          cancellation_reason?: string | null
          cancellation_comment?: string | null
          stage_entered_at?: string | null
          stage_deadline_override_hours?: number | null
          overdue_notified_at?: string | null
          cancelled_at?: string | null
          cancelled_by?: string | null
          incoterms?: string | null
          procurement_substatus?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          customer_id?: string | null
          idn_quote?: string
          title?: string
          description?: string | null
          status?: string
          valid_until?: string | null
          subtotal?: number
          tax_rate?: number | null
          tax_amount?: number | null
          total_amount?: number
          notes?: string | null
          terms_conditions?: string | null
          created_by?: string
          created_at?: string | null
          updated_at?: string | null
          quote_date?: string
          deleted_at?: string | null
          delivery_address?: string | null
          contact_id?: string | null
          created_by_user_id?: string | null
          manager_name?: string | null
          manager_phone?: string | null
          manager_email?: string | null
          workflow_state?: string
          logistics_complete?: boolean | null
          customs_complete?: boolean | null
          current_assignee_role?: string | null
          assigned_at?: string | null
          senior_approvals_required?: number | null
          senior_approvals_received?: number | null
          current_version?: number | null
          accepted_version_id?: string | null
          last_financial_comment?: string | null
          last_sendback_reason?: string | null
          financial_reviewed_at?: string | null
          financial_reviewed_by?: string | null
          submission_comment?: string | null
          last_approval_comment?: string | null
          current_version_id?: string | null
          total_usd?: number | null
          total_quote_currency?: number | null
          last_calculated_at?: string | null
          version_count?: number
          currency?: string
          total_profit_usd?: number | null
          total_vat_on_import_usd?: number | null
          total_vat_payable_usd?: number | null
          usd_to_quote_rate?: number | null
          exchange_rate_source?: string | null
          exchange_rate_timestamp?: string | null
          total_amount_quote?: number | null
          total_with_vat_quote?: number | null
          total_with_vat_usd?: number | null
          payment_terms?: string | null
          delivery_days?: number | null
          delivery_terms?: string | null
          document_folder_link?: string | null
          executor_user_id?: string | null
          spec_sign_date?: string | null
          total_quantity?: number | null
          total_weight_kg?: number | null
          delivery_city?: string | null
          cargo_type?: string | null
          deal_type?: string | null
          assigned_procurement_users?: Json | null
          assigned_logistics_user?: string | null
          assigned_customs_user?: string | null
          procurement_completed_at?: string | null
          logistics_completed_at?: string | null
          customs_completed_at?: string | null
          workflow_status?: string | null
          approvals?: Json | null
          seller_company_id?: string | null
          delivery_country?: string | null
          delivery_method?: string | null
          revision_department?: string | null
          revision_comment?: string | null
          revision_returned_at?: string | null
          approval_reason?: string | null
          approval_justification?: string | null
          needs_justification?: boolean | null
          exchange_rate_to_usd?: number | null
          subtotal_usd?: number | null
          total_amount_usd?: number | null
          sent_at?: string | null
          sent_to_email?: string | null
          partial_recalc?: string | null
          rejection_reason?: string | null
          rejection_comment?: string | null
          rejected_at?: string | null
          rejected_by?: string | null
          validity_days?: number | null
          delivery_priority?: string | null
          contact_person_id?: string | null
          sales_checklist?: Json | null
          profit_quote_currency?: number | null
          quote_controller_id?: string | null
          quote_control_completed_at?: string | null
          spec_controller_id?: string | null
          spec_control_completed_at?: string | null
          additional_info?: string | null
          is_phmb?: boolean
          phmb_advance_pct?: number | null
          phmb_markup_pct?: number | null
          phmb_payment_days?: number | null
          cogs_quote_currency?: number | null
          revenue_no_vat_quote_currency?: number | null
          idn?: string | null
          tender_type?: string | null
          competitors?: string | null
          cancellation_reason?: string | null
          cancellation_comment?: string | null
          stage_entered_at?: string | null
          stage_deadline_override_hours?: number | null
          overdue_notified_at?: string | null
          cancelled_at?: string | null
          cancelled_by?: string | null
          incoterms?: string | null
          procurement_substatus?: string | null
        }
        Relationships: []
      }
      registration_requests: {
        Row: {
          id: string
          first_name: string
          last_name: string
          email: string
          phone: string | null
          position: string | null
          department: string | null
          manager: string | null
          status: string
          created_at: string
        }
        Insert: {
          id?: string
          first_name: string
          last_name: string
          email: string
          phone?: string | null
          position?: string | null
          department?: string | null
          manager?: string | null
          status?: string
          created_at?: string
        }
        Update: {
          id?: string
          first_name?: string
          last_name?: string
          email?: string
          phone?: string | null
          position?: string | null
          department?: string | null
          manager?: string | null
          status?: string
          created_at?: string
        }
        Relationships: []
      }
      roles: {
        Row: {
          id: string
          organization_id: string | null
          name: string
          slug: string
          description: string | null
          permissions: Json | null
          is_system_role: boolean | null
          is_default: boolean | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          organization_id?: string | null
          name: string
          slug: string
          description?: string | null
          permissions?: Json | null
          is_system_role?: boolean | null
          is_default?: boolean | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string | null
          name?: string
          slug?: string
          description?: string | null
          permissions?: Json | null
          is_system_role?: boolean | null
          is_default?: boolean | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      route_logistics_assignments: {
        Row: {
          id: string
          organization_id: string
          route_pattern: string
          user_id: string
          created_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          route_pattern: string
          user_id: string
          created_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          route_pattern?: string
          user_id?: string
          created_at?: string
          created_by?: string | null
        }
        Relationships: []
      }
      route_procurement_group_assignments: {
        Row: {
          id: string
          organization_id: string
          sales_group_id: string
          user_id: string
          created_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          sales_group_id: string
          user_id: string
          created_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          sales_group_id?: string
          user_id?: string
          created_at?: string
          created_by?: string | null
        }
        Relationships: []
      }
      sales_groups: {
        Row: {
          id: string
          name: string
          description: string | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          name: string
          description?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          name?: string
          description?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      seller_companies: {
        Row: {
          id: string
          organization_id: string
          name: string
          supplier_code: string
          country: string | null
          is_active: boolean | null
          created_at: string | null
          updated_at: string | null
          general_director_last_name: string | null
          general_director_first_name: string | null
          general_director_patronymic: string | null
          general_director_position: string | null
          inn: string | null
          kpp: string | null
          ogrn: string | null
          registration_address: string | null
          phone: string | null
          email: string | null
          website: string | null
          bank_name: string | null
          bik: string | null
          correspondent_account: string | null
          payment_account: string | null
          invoice_validity_days: number | null
          general_director_name: string | null
          address: string | null
          tax_id: string | null
          region: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          name: string
          supplier_code: string
          country?: string | null
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          general_director_last_name?: string | null
          general_director_first_name?: string | null
          general_director_patronymic?: string | null
          general_director_position?: string | null
          inn?: string | null
          kpp?: string | null
          ogrn?: string | null
          registration_address?: string | null
          phone?: string | null
          email?: string | null
          website?: string | null
          bank_name?: string | null
          bik?: string | null
          correspondent_account?: string | null
          payment_account?: string | null
          invoice_validity_days?: number | null
          general_director_name?: string | null
          address?: string | null
          tax_id?: string | null
          region?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          name?: string
          supplier_code?: string
          country?: string | null
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          general_director_last_name?: string | null
          general_director_first_name?: string | null
          general_director_patronymic?: string | null
          general_director_position?: string | null
          inn?: string | null
          kpp?: string | null
          ogrn?: string | null
          registration_address?: string | null
          phone?: string | null
          email?: string | null
          website?: string | null
          bank_name?: string | null
          bik?: string | null
          correspondent_account?: string | null
          payment_account?: string | null
          invoice_validity_days?: number | null
          general_director_name?: string | null
          address?: string | null
          tax_id?: string | null
          region?: string | null
        }
        Relationships: []
      }
      specification_exports: {
        Row: {
          id: string
          organization_id: string
          quote_id: string
          contract_id: string
          specification_number: number
          specification_date: string
          export_data: Json
          created_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          quote_id: string
          contract_id: string
          specification_number: number
          specification_date?: string
          export_data?: Json
          created_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          quote_id?: string
          contract_id?: string
          specification_number?: number
          specification_date?: string
          export_data?: Json
          created_at?: string
          created_by?: string | null
        }
        Relationships: []
      }
      specification_payments: {
        Row: {
          id: string
          organization_id: string
          specification_id: string
          payment_date: string
          amount: number
          currency: string
          category: string
          payment_number: number
          comment: string | null
          created_by: string | null
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          specification_id: string
          payment_date: string
          amount: number
          currency?: string
          category: string
          payment_number: number
          comment?: string | null
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          specification_id?: string
          payment_date?: string
          amount?: number
          currency?: string
          category?: string
          payment_number?: number
          comment?: string | null
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      specifications: {
        Row: {
          id: string
          quote_id: string
          quote_version_id: string | null
          organization_id: string
          specification_number: string | null
          proposal_idn: string | null
          sign_date: string | null
          validity_period: string | null
          specification_currency: string | null
          exchange_rate_to_ruble: number | null
          client_payment_terms: string | null
          cargo_pickup_country: string | null
          readiness_period: string | null
          delivery_city_russia: string | null
          cargo_type: string | null
          logistics_period: string | null
          our_legal_entity: string | null
          client_legal_entity: string | null
          signed_scan_url: string | null
          status: string
          created_by: string | null
          created_at: string | null
          updated_at: string | null
          approvals: Json | null
          advance_percent_from_client: number | null
          payment_deferral_days: number | null
          delivery_period_days: number | null
          days_from_delivery_to_advance: number | null
          comment: string | null
          actual_delivery_date: string | null
          planned_dovoz_date: string | null
          priority_tag: string | null
          client_payment_term_after_upd: number | null
          contract_id: string | null
          item_ind_sku: string | null
          goods_shipment_country: string | null
          supplier_payment_country: string | null
          delivery_days_type: string | null
          delivery_days: number | null
          signed_scan_document_id: string | null
          specification_date: string | null
          export_data: Json | null
        }
        Insert: {
          id?: string
          quote_id: string
          quote_version_id?: string | null
          organization_id: string
          specification_number?: string | null
          proposal_idn?: string | null
          sign_date?: string | null
          validity_period?: string | null
          specification_currency?: string | null
          exchange_rate_to_ruble?: number | null
          client_payment_terms?: string | null
          cargo_pickup_country?: string | null
          readiness_period?: string | null
          delivery_city_russia?: string | null
          cargo_type?: string | null
          logistics_period?: string | null
          our_legal_entity?: string | null
          client_legal_entity?: string | null
          signed_scan_url?: string | null
          status?: string
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
          approvals?: Json | null
          advance_percent_from_client?: number | null
          payment_deferral_days?: number | null
          delivery_period_days?: number | null
          days_from_delivery_to_advance?: number | null
          comment?: string | null
          actual_delivery_date?: string | null
          planned_dovoz_date?: string | null
          priority_tag?: string | null
          client_payment_term_after_upd?: number | null
          contract_id?: string | null
          item_ind_sku?: string | null
          goods_shipment_country?: string | null
          supplier_payment_country?: string | null
          delivery_days_type?: string | null
          delivery_days?: number | null
          signed_scan_document_id?: string | null
          specification_date?: string | null
          export_data?: Json | null
        }
        Update: {
          id?: string
          quote_id?: string
          quote_version_id?: string | null
          organization_id?: string
          specification_number?: string | null
          proposal_idn?: string | null
          sign_date?: string | null
          validity_period?: string | null
          specification_currency?: string | null
          exchange_rate_to_ruble?: number | null
          client_payment_terms?: string | null
          cargo_pickup_country?: string | null
          readiness_period?: string | null
          delivery_city_russia?: string | null
          cargo_type?: string | null
          logistics_period?: string | null
          our_legal_entity?: string | null
          client_legal_entity?: string | null
          signed_scan_url?: string | null
          status?: string
          created_by?: string | null
          created_at?: string | null
          updated_at?: string | null
          approvals?: Json | null
          advance_percent_from_client?: number | null
          payment_deferral_days?: number | null
          delivery_period_days?: number | null
          days_from_delivery_to_advance?: number | null
          comment?: string | null
          actual_delivery_date?: string | null
          planned_dovoz_date?: string | null
          priority_tag?: string | null
          client_payment_term_after_upd?: number | null
          contract_id?: string | null
          item_ind_sku?: string | null
          goods_shipment_country?: string | null
          supplier_payment_country?: string | null
          delivery_days_type?: string | null
          delivery_days?: number | null
          signed_scan_document_id?: string | null
          specification_date?: string | null
          export_data?: Json | null
        }
        Relationships: []
      }
      stage_deadlines: {
        Row: {
          id: string
          organization_id: string
          stage: string
          deadline_hours: number
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          stage: string
          deadline_hours?: number
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          stage?: string
          deadline_hours?: number
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      status_history: {
        Row: {
          id: string
          quote_id: string
          from_status: string | null
          from_substatus: string | null
          to_status: string | null
          to_substatus: string | null
          transitioned_at: string
          transitioned_by: string
          reason: string
        }
        Insert: {
          id?: string
          quote_id: string
          from_status?: string | null
          from_substatus?: string | null
          to_status?: string | null
          to_substatus?: string | null
          transitioned_at?: string
          transitioned_by: string
          reason?: string
        }
        Update: {
          id?: string
          quote_id?: string
          from_status?: string | null
          from_substatus?: string | null
          to_status?: string | null
          to_substatus?: string | null
          transitioned_at?: string
          transitioned_by?: string
          reason?: string
        }
        Relationships: []
      }
      supplier_assignees: {
        Row: {
          supplier_id: string
          user_id: string
          created_at: string
          created_by: string | null
        }
        Insert: {
          supplier_id: string
          user_id: string
          created_at?: string
          created_by?: string | null
        }
        Update: {
          supplier_id?: string
          user_id?: string
          created_at?: string
          created_by?: string | null
        }
        Relationships: []
      }
      supplier_contacts: {
        Row: {
          id: string
          supplier_id: string
          organization_id: string
          name: string
          position: string | null
          email: string | null
          phone: string | null
          is_primary: boolean | null
          notes: string | null
          created_at: string | null
          updated_at: string | null
          created_by: string | null
        }
        Insert: {
          id?: string
          supplier_id: string
          organization_id: string
          name: string
          position?: string | null
          email?: string | null
          phone?: string | null
          is_primary?: boolean | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
          created_by?: string | null
        }
        Update: {
          id?: string
          supplier_id?: string
          organization_id?: string
          name?: string
          position?: string | null
          email?: string | null
          phone?: string | null
          is_primary?: boolean | null
          notes?: string | null
          created_at?: string | null
          updated_at?: string | null
          created_by?: string | null
        }
        Relationships: []
      }
      supplier_countries: {
        Row: {
          code: string
          name_ru: string
          vat_rate: number
          internal_markup_ru: number
          internal_markup_tr: number
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          code: string
          name_ru: string
          vat_rate: number
          internal_markup_ru: number
          internal_markup_tr: number
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          code?: string
          name_ru?: string
          vat_rate?: number
          internal_markup_ru?: number
          internal_markup_tr?: number
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      supplier_invoice_items: {
        Row: {
          id: string
          invoice_id: string
          quote_item_id: string | null
          description: string | null
          quantity: number
          unit_price: number
          total_price: number
          unit: string | null
          created_at: string | null
        }
        Insert: {
          id?: string
          invoice_id: string
          quote_item_id?: string | null
          description?: string | null
          quantity?: number
          unit_price: number
          total_price: number
          unit?: string | null
          created_at?: string | null
        }
        Update: {
          id?: string
          invoice_id?: string
          quote_item_id?: string | null
          description?: string | null
          quantity?: number
          unit_price?: number
          total_price?: number
          unit?: string | null
          created_at?: string | null
        }
        Relationships: []
      }
      supplier_invoice_payments: {
        Row: {
          id: string
          invoice_id: string
          payment_date: string
          amount: number
          currency: string
          exchange_rate: number | null
          payment_type: string
          buyer_company_id: string | null
          payment_document: string | null
          notes: string | null
          created_at: string
          updated_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          invoice_id: string
          payment_date: string
          amount: number
          currency?: string
          exchange_rate?: number | null
          payment_type?: string
          buyer_company_id?: string | null
          payment_document?: string | null
          notes?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          invoice_id?: string
          payment_date?: string
          amount?: number
          currency?: string
          exchange_rate?: number | null
          payment_type?: string
          buyer_company_id?: string | null
          payment_document?: string | null
          notes?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
        Relationships: []
      }
      supplier_invoices: {
        Row: {
          id: string
          organization_id: string
          supplier_id: string
          invoice_number: string
          invoice_date: string
          due_date: string | null
          total_amount: number
          currency: string | null
          status: string
          notes: string | null
          invoice_file_url: string | null
          created_at: string | null
          updated_at: string | null
          created_by: string | null
          pickup_location_id: string | null
          pickup_country: string | null
          total_weight_kg: number | null
          total_volume_m3: number | null
        }
        Insert: {
          id?: string
          organization_id: string
          supplier_id: string
          invoice_number: string
          invoice_date: string
          due_date?: string | null
          total_amount: number
          currency?: string | null
          status?: string
          notes?: string | null
          invoice_file_url?: string | null
          created_at?: string | null
          updated_at?: string | null
          created_by?: string | null
          pickup_location_id?: string | null
          pickup_country?: string | null
          total_weight_kg?: number | null
          total_volume_m3?: number | null
        }
        Update: {
          id?: string
          organization_id?: string
          supplier_id?: string
          invoice_number?: string
          invoice_date?: string
          due_date?: string | null
          total_amount?: number
          currency?: string | null
          status?: string
          notes?: string | null
          invoice_file_url?: string | null
          created_at?: string | null
          updated_at?: string | null
          created_by?: string | null
          pickup_location_id?: string | null
          pickup_country?: string | null
          total_weight_kg?: number | null
          total_volume_m3?: number | null
        }
        Relationships: []
      }
      suppliers: {
        Row: {
          id: string
          organization_id: string
          name: string
          country: string | null
          is_active: boolean | null
          created_at: string | null
          updated_at: string | null
          supplier_code: string | null
          city: string | null
          inn: string | null
          kpp: string | null
          contact_person: string | null
          contact_email: string | null
          contact_phone: string | null
          default_payment_terms: string | null
          created_by: string | null
          registration_number: string | null
          notes: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          name: string
          country?: string | null
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          supplier_code?: string | null
          city?: string | null
          inn?: string | null
          kpp?: string | null
          contact_person?: string | null
          contact_email?: string | null
          contact_phone?: string | null
          default_payment_terms?: string | null
          created_by?: string | null
          registration_number?: string | null
          notes?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          name?: string
          country?: string | null
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          supplier_code?: string | null
          city?: string | null
          inn?: string | null
          kpp?: string | null
          contact_person?: string | null
          contact_email?: string | null
          contact_phone?: string | null
          default_payment_terms?: string | null
          created_by?: string | null
          registration_number?: string | null
          notes?: string | null
        }
        Relationships: []
      }
      svh: {
        Row: {
          id: string
          name: string
          code: string | null
          address: string | null
          contact_info: string | null
          is_active: boolean | null
          created_at: string | null
          updated_at: string | null
          city: string | null
          country: string | null
          contour: string | null
        }
        Insert: {
          id?: string
          name: string
          code?: string | null
          address?: string | null
          contact_info?: string | null
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          city?: string | null
          country?: string | null
          contour?: string | null
        }
        Update: {
          id?: string
          name?: string
          code?: string | null
          address?: string | null
          contact_info?: string | null
          is_active?: boolean | null
          created_at?: string | null
          updated_at?: string | null
          city?: string | null
          country?: string | null
          contour?: string | null
        }
        Relationships: []
      }
      telegram_users: {
        Row: {
          id: string
          user_id: string
          telegram_id: number
          telegram_username: string | null
          is_verified: boolean | null
          verification_code: string | null
          verification_code_expires_at: string | null
          created_at: string | null
          verified_at: string | null
        }
        Insert: {
          id?: string
          user_id: string
          telegram_id: number
          telegram_username?: string | null
          is_verified?: boolean | null
          verification_code?: string | null
          verification_code_expires_at?: string | null
          created_at?: string | null
          verified_at?: string | null
        }
        Update: {
          id?: string
          user_id?: string
          telegram_id?: number
          telegram_username?: string | null
          is_verified?: boolean | null
          verification_code?: string | null
          verification_code_expires_at?: string | null
          created_at?: string | null
          verified_at?: string | null
        }
        Relationships: []
      }
      tender_routing_chain: {
        Row: {
          id: string
          organization_id: string
          step_order: number
          user_id: string
          role_label: string
          created_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          step_order: number
          user_id: string
          role_label: string
          created_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          step_order?: number
          user_id?: string
          role_label?: string
          created_at?: string
          created_by?: string | null
        }
        Relationships: []
      }
      training_videos: {
        Row: {
          id: string
          organization_id: string
          title: string
          description: string | null
          youtube_id: string
          category: string
          sort_order: number
          is_active: boolean
          created_by: string | null
          created_at: string
          updated_at: string
          platform: string
          thumbnail_url: string | null
        }
        Insert: {
          id?: string
          organization_id: string
          title: string
          description?: string | null
          youtube_id: string
          category?: string
          sort_order?: number
          is_active?: boolean
          created_by?: string | null
          created_at?: string
          updated_at?: string
          platform?: string
          thumbnail_url?: string | null
        }
        Update: {
          id?: string
          organization_id?: string
          title?: string
          description?: string | null
          youtube_id?: string
          category?: string
          sort_order?: number
          is_active?: boolean
          created_by?: string | null
          created_at?: string
          updated_at?: string
          platform?: string
          thumbnail_url?: string | null
        }
        Relationships: []
      }
      user_feedback: {
        Row: {
          id: string
          short_id: string
          user_id: string | null
          user_email: string | null
          user_name: string | null
          organization_id: string | null
          organization_name: string | null
          page_url: string
          page_title: string | null
          user_agent: string | null
          feedback_type: string
          description: string
          debug_context: Json | null
          status: string | null
          created_at: string | null
          screenshot_data: string | null
          clickup_task_id: string | null
          updated_at: string | null
          screenshot_url: string | null
        }
        Insert: {
          id?: string
          short_id: string
          user_id?: string | null
          user_email?: string | null
          user_name?: string | null
          organization_id?: string | null
          organization_name?: string | null
          page_url: string
          page_title?: string | null
          user_agent?: string | null
          feedback_type: string
          description: string
          debug_context?: Json | null
          status?: string | null
          created_at?: string | null
          screenshot_data?: string | null
          clickup_task_id?: string | null
          updated_at?: string | null
          screenshot_url?: string | null
        }
        Update: {
          id?: string
          short_id?: string
          user_id?: string | null
          user_email?: string | null
          user_name?: string | null
          organization_id?: string | null
          organization_name?: string | null
          page_url?: string
          page_title?: string | null
          user_agent?: string | null
          feedback_type?: string
          description?: string
          debug_context?: Json | null
          status?: string | null
          created_at?: string | null
          screenshot_data?: string | null
          clickup_task_id?: string | null
          updated_at?: string | null
          screenshot_url?: string | null
        }
        Relationships: []
      }
      user_profiles: {
        Row: {
          id: string
          user_id: string
          organization_id: string
          full_name: string | null
          position: string | null
          department_id: string | null
          sales_group_id: string | null
          manager_id: string | null
          phone: string | null
          location: string | null
          created_at: string | null
          updated_at: string | null
          date_of_birth: string | null
          hire_date: string | null
          timezone: string | null
          bio: string | null
        }
        Insert: {
          id?: string
          user_id: string
          organization_id: string
          full_name?: string | null
          position?: string | null
          department_id?: string | null
          sales_group_id?: string | null
          manager_id?: string | null
          phone?: string | null
          location?: string | null
          created_at?: string | null
          updated_at?: string | null
          date_of_birth?: string | null
          hire_date?: string | null
          timezone?: string | null
          bio?: string | null
        }
        Update: {
          id?: string
          user_id?: string
          organization_id?: string
          full_name?: string | null
          position?: string | null
          department_id?: string | null
          sales_group_id?: string | null
          manager_id?: string | null
          phone?: string | null
          location?: string | null
          created_at?: string | null
          updated_at?: string | null
          date_of_birth?: string | null
          hire_date?: string | null
          timezone?: string | null
          bio?: string | null
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          id: string
          user_id: string
          organization_id: string
          role_id: string
          created_at: string | null
          created_by: string | null
        }
        Insert: {
          id?: string
          user_id: string
          organization_id: string
          role_id: string
          created_at?: string | null
          created_by?: string | null
        }
        Update: {
          id?: string
          user_id?: string
          organization_id?: string
          role_id?: string
          created_at?: string | null
          created_by?: string | null
        }
        Relationships: []
      }
      user_settings: {
        Row: {
          id: string
          user_id: string
          setting_key: string
          setting_value: Json
          created_at: string | null
          updated_at: string | null
        }
        Insert: {
          id?: string
          user_id: string
          setting_key: string
          setting_value?: Json
          created_at?: string | null
          updated_at?: string | null
        }
        Update: {
          id?: string
          user_id?: string
          setting_key?: string
          setting_value?: Json
          created_at?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      user_table_views: {
        Row: {
          id: string
          user_id: string
          table_key: string
          name: string
          filters: Json
          sort: string | null
          visible_columns: Json
          is_shared: boolean
          organization_id: string | null
          is_default: boolean
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          table_key: string
          name: string
          filters?: Json
          sort?: string | null
          visible_columns?: Json
          is_shared?: boolean
          organization_id?: string | null
          is_default?: boolean
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          table_key?: string
          name?: string
          filters?: Json
          sort?: string | null
          visible_columns?: Json
          is_shared?: boolean
          organization_id?: string | null
          is_default?: boolean
          created_at?: string
          updated_at?: string
        }
        Relationships: []
      }
      vat_rates_by_country: {
        Row: {
          country_code: string
          rate: number
          notes: string | null
          updated_at: string
          updated_by: string | null
        }
        Insert: {
          country_code: string
          rate?: number
          notes?: string | null
          updated_at?: string
          updated_by?: string | null
        }
        Update: {
          country_code?: string
          rate?: number
          notes?: string | null
          updated_at?: string
          updated_by?: string | null
        }
        Relationships: []
      }
      workflow_transitions: {
        Row: {
          id: string
          quote_id: string
          from_status: string
          to_status: string
          actor_id: string
          actor_role: string
          comment: string | null
          created_at: string | null
        }
        Insert: {
          id?: string
          quote_id: string
          from_status: string
          to_status: string
          actor_id: string
          actor_role: string
          comment?: string | null
          created_at?: string | null
        }
        Update: {
          id?: string
          quote_id?: string
          from_status?: string
          to_status?: string
          actor_id?: string
          actor_role?: string
          comment?: string | null
          created_at?: string | null
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
  }
}

