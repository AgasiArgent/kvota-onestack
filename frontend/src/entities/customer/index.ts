export type {
  Customer,
  CustomerContact,
  CustomerCall,
  CustomerContract,
  CustomerListItem,
  CustomerFinancials,
  CustomerStats,
  PhoneEntry,
  ContractFormData,
} from "./types";
export {
  fetchCustomersList,
  fetchCustomerFinancials,
  fetchCustomerDetail,
  fetchCustomerStats,
  fetchCustomerContacts,
  fetchCustomerContracts,
  fetchCustomerCalls,
  fetchCustomerQuotes,
  fetchCustomerSpecs,
  fetchCustomerPositions,
  fetchOrgUsers,
} from "./queries";
export type {
  ContactFormData,
  CallFormData,
  AddressFormData,
} from "./mutations";
export {
  createCustomer,
  createContact,
  updateContact,
  deleteContact,
  createCall,
  updateCustomerNotes,
  updateCustomerAddresses,
  updateCustomerGeneralEmail,
  createContract,
  updateContract,
  deleteContract,
} from "./mutations";
