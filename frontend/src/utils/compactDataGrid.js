export const COMPACT_MAIN_PAGE_SIZE_OPTIONS = [10, 20, 50];
export const COMPACT_LOCAL_PAGE_SIZE_OPTIONS = [10, 20, 50];
export const COMPACT_DIALOG_PAGE_SIZE_OPTIONS = [10, 20, 50];

export const compactGridSx = {
  height: "100%",
  border: 0,
  backgroundColor: "white",
  "& .MuiDataGrid-columnHeaders": {
    backgroundColor: "#f7f9fc"
  }
};

export const compactGridProps = {
  density: "standard",
  rowHeight: 57,
  columnHeaderHeight: 57,
  disableColumnFilter: true
};
