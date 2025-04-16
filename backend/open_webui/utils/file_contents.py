def is_spreadsheet_file(filename=None, content_type=None):
    """
    Determines if a file is a spreadsheet (CSV or Excel) based on content type or filename.
    
    Args:
        filename (str, optional): The name of the file
        content_type (str, optional): The MIME type of the file
        
    Returns:
        bool: True if the file is either a CSV or Excel file, False otherwise
    """
    # Check if it's a CSV file
    is_csv = (
        content_type == 'text/csv' or 
        (filename and filename.lower().endswith('.csv'))
    )
    
    # Check if it's an Excel file (XLSX or XLS)
    is_xlsx = (
        content_type in [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel'
        ] or (filename and (filename.lower().endswith('.xlsx') or filename.lower().endswith('.xls')))
    )
    
    # Return True if it's either a CSV or Excel file
    return is_csv or is_xlsx