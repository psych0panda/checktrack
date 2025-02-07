import {
  Container,
  Heading,
  SkeletonText,
  Table,
  TableContainer,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "@chakra-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect } from "react"
import { z } from "zod"

import { ItemsService } from "../../client/index.ts"
import ActionsMenu from "../../components/Common/ActionsMenu.tsx"
import Navbar from "../../components/Common/Navbar.tsx"
import AddInvoice from "../../components/Invoices/AddItem.tsx"
import { PaginationFooter } from "../../components/Common/PaginationFooter.tsx"

const invoiceSearchSchema = z.object({
  page: z.number().catch(1),
})

export const Route = createFileRoute("/_layout/invoice")({
  component: Invoice,
  validateSearch: (search) => invoiceSearchSchema.parse(search),
})

const PER_PAGE = 5

function getInvoiceQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      ItemsService.readInvoices({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["invoices", { page }],
  }
}

function InvoiceTable() {
  const queryClient = useQueryClient()
  const { page } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const setPage = (page: number) =>
    navigate({ search: (prev: { [key: string]: string }) => ({ ...prev, page }) })

  const {
    data: invoices,
    isPending,
    isPlaceholderData,
  } = useQuery({
    ...getInvoiceQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const hasNextPage = !isPlaceholderData && invoices?.data.length === PER_PAGE
  const hasPreviousPage = page > 1

  useEffect(() => {
    if (hasNextPage) {
      queryClient.prefetchQuery(getInvoiceQueryOptions({ page: page + 1 }))
    }
  }, [page, queryClient, hasNextPage])

  return (
    <>
      <TableContainer>
        <Table size={{ base: "sm", md: "md" }}>
          <Thead>
            <Tr>
              <Th>ID</Th>
              <Th>Serial</Th>
              <Th>User</Th>
              <Th>Total Amount</Th>
              <Th>Date of issue</Th>
              <Th>Linked Pay</Th>
            </Tr>
          </Thead>
          {isPending ? (
            <Tbody>
              <Tr>
                {new Array(4).fill(null).map((_, index) => (
                  <Td key={index}>
                    <SkeletonText noOfLines={1} paddingBlock="16px" />
                  </Td>
                ))}
              </Tr>
            </Tbody>
          ) : (
            <Tbody>
              {invoices?.data.map((invoice) => (
                <Tr key={invoice.id} opacity={isPlaceholderData ? 0.5 : 1}>
                  <Td>{invoice.id}</Td>
                  <Td isTruncated maxWidth="150px">
                    {invoice.serial_number}
                  </Td>
                  <Td
                    color={!invoice.user_id ? "ui.dim" : "inherit"}
                    isTruncated
                    maxWidth="150px"
                  >
                    {invoice.payment_id || "N/A"}
                  </Td>
                  <Td>
                    <ActionsMenu type={"Invoice"} value={invoice} />
                  </Td>
                </Tr>
              ))}
            </Tbody>
          )}
        </Table>
      </TableContainer>
      <PaginationFooter
        page={page}
        onChangePage={setPage}
        hasNextPage={hasNextPage}
        hasPreviousPage={hasPreviousPage}
      />
    </>
  )
}

function Invocies() {
  return (
    <Container maxW="full">
      <Heading size="lg" textAlign={{ base: "center", md: "left" }} pt={12}>
      Invocie Management
      </Heading>

      <Navbar type={"Invoice"} addModalAs={AddInvoice} />
      <InvoiceTable />
    </Container>
  )
}
