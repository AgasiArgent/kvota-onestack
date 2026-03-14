export type {
  Customer,
  CustomerContact,
  CustomerCall,
  CustomerListItem,
  CustomerStats,
} from "./types";
export {
  fetchCustomersList,
  fetchCustomerDetail,
  fetchCustomerStats,
  fetchCustomerContacts,
  fetchCustomerCalls,
  fetchCustomerQuotes,
  fetchCustomerSpecs,
  fetchCustomerPositions,
} from "./queries";
export type {
  ContactFormData,
  CallFormData,
  AddressFormData,
} from "./mutations";
export {
  createContact,
  updateContact,
  deleteContact,
  createCall,
  updateCustomerNotes,
  updateCustomerAddresses,
} from "./mutations";
