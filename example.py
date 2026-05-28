for i in range(arr):
    j = i + 1
    while(j < len(arr)):
        if(nums[i] <= nums[j]:
            j +=1
        else:
            min = nums[j]
            nums[j] = nums[i]
            nums[i] = min
            j+=1
    
    