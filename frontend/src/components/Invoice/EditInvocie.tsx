import {
  Button,
  FormControl,
  FormErrorMessage,
  FormLabel,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { type SubmitHandler, useForm } from "react-hook-form"

import {
  type ApiError,
  type InvoicePublic,
  type InvoiceUpdate,
  InvoiceService,
} from "../../client"
import useCustomToast from "../../hooks/useCustomToast"
import { handleError } from "../../utils"

interface EditInvocieProps {
  item: InvoicePublic
  isOpen: boolean
  onClose: () => void
}

const EditInvoice = ({ invoice, isOpen, onClose }: EditInvoiceProps) => {
  const queryClient = useQueryClient()
  const showToast = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { isSubmitting, errors, isDirty },
  } = useForm<InvoiceUpdate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: invocie,
  })

  const mutation = useMutation({
    mutationFn: (data: InvoiceUpdate) =>
      InvoiceService.updateInvoice({ id: invoice.id, requestBody: data }),
    onSuccess: () => {
      showToast("Success!", "Invoice updated successfully.", "success")
      onClose()
    },
    onError: (err: ApiError) => {
      handleError(err, showToast)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["invocie"] })
    },
  })

  const onSubmit: SubmitHandler<InvocieUpdate> = async (data) => {
    mutation.mutate(data)
  }

  const onCancel = () => {
    reset()
    onClose()
  }

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        size={{ base: "sm", md: "md" }}
        isCentered
      >
        <ModalOverlay />
        <ModalContent as="form" onSubmit={handleSubmit(onSubmit)}>
          <ModalHeader>Edit Invoice</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <FormControl isInvalid={!!errors.title}>
              <FormLabel htmlFor="title">Linked Pay</FormLabel>
              <Input
                id="payment"
                {...register("payment"
                })}
                type="text"
              />
              {errors.title && (
                <FormErrorMessage>{errors.title.message}</FormErrorMessage>
              )}
            </FormControl>
            <FormControl mt={4}>
              <FormLabel htmlFor="description">Products</FormLabel>
              <Input
                id="products"
                {...register("products")}
                placeholder="Products"
                type="text"
              />
            </FormControl>
          </ModalBody>
          <ModalFooter gap={3}>
            <Button
              variant="primary"
              type="submit"
              isLoading={isSubmitting}
              isDisabled={!isDirty}
            >
              Save
            </Button>
            <Button onClick={onCancel}>Cancel</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  )
}

export default EditInvoice
